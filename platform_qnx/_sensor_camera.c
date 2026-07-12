/* CPython binding for QNX Sensor Framework Camera API (NV12 viewfinder). */
#define PY_SSIZE_T_CLEAN
#define Py_LIMITED_API 0x03080000
#include <Python.h>
#include <camera/camera_api.h>
#include <pthread.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    camera_handle_t handle;
    pthread_mutex_t lock;
    pthread_cond_t ready;
    uint8_t *frame;
    size_t frame_size;
    uint32_t width;
    uint32_t height;
    int64_t timestamp_us;
    double fps;
    uint64_t sequence;
    uint64_t delivered_sequence;
    int streaming;
} capture_context_t;

static void destroy_context(capture_context_t *context) {
    if (context == NULL) {
        return;
    }
    if (context->streaming) {
        camera_stop_viewfinder(context->handle);
        camera_close(context->handle);
    }
    pthread_cond_destroy(&context->ready);
    pthread_mutex_destroy(&context->lock);
    free(context->frame);
    free(context);
}

static void copy_nv12(camera_handle_t handle, camera_buffer_t *buffer, void *argument) {
    capture_context_t *context = argument;
    const camera_frame_nv12_t *descriptor;
    size_t packed_size;
    uint32_t row;

    (void)handle;
    if (buffer->frametype != CAMERA_FRAMETYPE_NV12) {
        return;
    }
    descriptor = &buffer->framedesc.nv12;
    packed_size = (size_t)descriptor->width * descriptor->height * 3 / 2;

    pthread_mutex_lock(&context->lock);
    if (context->frame_size != packed_size) {
        uint8_t *replacement = realloc(context->frame, packed_size);
        if (replacement == NULL) {
            pthread_mutex_unlock(&context->lock);
            return;
        }
        context->frame = replacement;
        context->frame_size = packed_size;
    }

    for (row = 0; row < descriptor->height; ++row) {
        memcpy(
            context->frame + (size_t)row * descriptor->width,
            buffer->framebuf + (size_t)row * descriptor->stride,
            descriptor->width
        );
    }
    for (row = 0; row < descriptor->height / 2; ++row) {
        memcpy(
            context->frame + (size_t)descriptor->width * descriptor->height +
                (size_t)row * descriptor->width,
            buffer->framebuf + descriptor->uv_offset + (size_t)row * descriptor->uv_stride,
            descriptor->width
        );
    }
    if (context->timestamp_us > 0 && buffer->frametimestamp > context->timestamp_us) {
        context->fps = 1000000.0 / (buffer->frametimestamp - context->timestamp_us);
    }
    context->width = descriptor->width;
    context->height = descriptor->height;
    context->timestamp_us = buffer->frametimestamp;
    ++context->sequence;
    pthread_cond_signal(&context->ready);
    pthread_mutex_unlock(&context->lock);
}

static void capsule_destructor(PyObject *capsule) {
    capture_context_t *context = PyCapsule_GetPointer(capsule, "reflex.qnx.camera");
    if (context == NULL) {
        PyErr_Clear();
        return;
    }
    destroy_context(context);
}

static PyObject *open_camera(PyObject *self, PyObject *args) {
    capture_context_t *context;
    unsigned int unit;
    camera_error_t error;
    (void)self;
    if (!PyArg_ParseTuple(args, "I", &unit)) {
        return NULL;
    }
    context = calloc(1, sizeof(*context));
    if (context == NULL) {
        return PyErr_NoMemory();
    }
    pthread_mutex_init(&context->lock, NULL);
    pthread_cond_init(&context->ready, NULL);
    error = camera_open((camera_unit_t)unit, CAMERA_MODE_PREAD, &context->handle);
    if (error != CAMERA_EOK) {
        PyErr_Format(PyExc_RuntimeError, "camera_open failed: %d", error);
        destroy_context(context);
        return NULL;
    }
    error = camera_set_vf_mode(context->handle, CAMERA_VFMODE_VIDEO);
    if (error == CAMERA_EOK) {
        error = camera_set_vf_property(context->handle, CAMERA_IMGPROP_FORMAT, CAMERA_FRAMETYPE_NV12);
    }
    if (error == CAMERA_EOK) {
        error = camera_set_vf_property(context->handle, CAMERA_IMGPROP_CREATEWINDOW, 0);
    }
    if (error == CAMERA_EOK) {
        error = camera_start_viewfinder(context->handle, copy_nv12, NULL, context);
    }
    if (error != CAMERA_EOK) {
        camera_close(context->handle);
        context->handle = 0;
        PyErr_Format(PyExc_RuntimeError, "Unable to start NV12 viewfinder: %d", error);
        destroy_context(context);
        return NULL;
    }
    context->streaming = 1;
    return PyCapsule_New(context, "reflex.qnx.camera", capsule_destructor);
}

static PyObject *read_nv12_frame(PyObject *self, PyObject *args) {
    PyObject *capsule;
    capture_context_t *context;
    PyObject *bytes;
    (void)self;
    if (!PyArg_ParseTuple(args, "O", &capsule)) {
        return NULL;
    }
    context = PyCapsule_GetPointer(capsule, "reflex.qnx.camera");
    if (context == NULL) {
        return NULL;
    }
    pthread_mutex_lock(&context->lock);
    while (context->sequence == context->delivered_sequence) {
        Py_BEGIN_ALLOW_THREADS
        pthread_cond_wait(&context->ready, &context->lock);
        Py_END_ALLOW_THREADS
    }
    bytes = PyBytes_FromStringAndSize((const char *)context->frame, context->frame_size);
    context->delivered_sequence = context->sequence;
    pthread_mutex_unlock(&context->lock);
    if (bytes == NULL) {
        return NULL;
    }
    return Py_BuildValue("NIId", bytes, context->width, context->height, context->fps);
}

static PyObject *close_camera(PyObject *self, PyObject *args) {
    PyObject *capsule;
    (void)self;
    if (!PyArg_ParseTuple(args, "O", &capsule)) {
        return NULL;
    }
    if (PyCapsule_SetDestructor(capsule, NULL) != 0) {
        return NULL;
    }
    capsule_destructor(capsule);
    if (PyCapsule_SetName(capsule, "reflex.qnx.camera.closed") != 0) {
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyMethodDef methods[] = {
    {"open_camera", open_camera, METH_VARARGS, "Open QNX Camera API viewfinder."},
    {"read_nv12_frame", read_nv12_frame, METH_VARARGS, "Read one packed NV12 frame."},
    {"close_camera", close_camera, METH_VARARGS, "Stop and close QNX Camera API viewfinder."},
    {NULL, NULL, 0, NULL},
};

static struct PyModuleDef module = {
    PyModuleDef_HEAD_INIT, "_sensor_camera", "QNX Sensor Framework bridge.", -1, methods,
};

PyMODINIT_FUNC PyInit__sensor_camera(void) {
    return PyModule_Create(&module);
}
