"""The icon of a macOS app, as macOS itself shows it in Finder and the Dock.

Asks NSWorkspace for the icon, so it works for every app: icons in an .icns file, icons in an
asset catalog (Assets.car, used by many newer apps such as Shottr) and apps without an icon.
Uses the Objective-C runtime through ctypes, so no pyobjc dependency is needed.
"""
import ctypes
import io
import os

from PIL import Image

_objc = ctypes.cdll.LoadLibrary('/usr/lib/libobjc.A.dylib')
ctypes.cdll.LoadLibrary('/System/Library/Frameworks/AppKit.framework/AppKit')
_objc.objc_getClass.restype = ctypes.c_void_p
_objc.objc_getClass.argtypes = [ctypes.c_char_p]
_objc.sel_registerName.restype = ctypes.c_void_p
_objc.sel_registerName.argtypes = [ctypes.c_char_p]
_objc.objc_autoreleasePoolPush.restype = ctypes.c_void_p
_objc.objc_autoreleasePoolPop.argtypes = [ctypes.c_void_p]

_MSG_SEND = ctypes.cast(_objc.objc_msgSend, ctypes.c_void_p).value


class _NSSize(ctypes.Structure):
    _fields_ = [('width', ctypes.c_double), ('height', ctypes.c_double)]


def _send(restype, *argtypes):
    """objc_msgSend with the exact prototype of one method (required on Apple silicon)."""
    return ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)(_MSG_SEND)


def _sel(name):
    return _objc.sel_registerName(name)


_send_id = _send(ctypes.c_void_p)
_send_id_str = _send(ctypes.c_void_p, ctypes.c_char_p)
_send_id_id = _send(ctypes.c_void_p, ctypes.c_void_p)
_send_size = _send(None, _NSSize)
_send_ulong = _send(ctypes.c_ulong)
_send_none = _send(None)
_send_cgimage = _send(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_send_representation = _send(ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p)

_NSString = _objc.objc_getClass(b'NSString')
_NSWorkspace = _objc.objc_getClass(b'NSWorkspace')
_NSBitmapImageRep = _objc.objc_getClass(b'NSBitmapImageRep')
_NSDictionary = _objc.objc_getClass(b'NSDictionary')
NS_PNG = 4  # NSBitmapImageFileTypePNG

# The icon is rendered at this size; callers scale it down to what they need.
RENDER_SIZE = 256  # points; a Retina screen gives 512 pixels, plenty for a 196 px key


def app_icon(app):
    """The app's icon as an RGBA image, or None if the path is not an app or the icon can't be read."""
    if not (app and app.endswith('.app') and os.path.isdir(app)):
        return None
    pool = _objc.objc_autoreleasePoolPush()
    try:
        path = _send_id_str(_NSString, _sel(b'stringWithUTF8String:'), os.fsencode(app))
        workspace = _send_id(_NSWorkspace, _sel(b'sharedWorkspace'))
        image = _send_id_id(workspace, _sel(b'iconForFile:'), path)
        if not image:
            return None
        # Render one bitmap at RENDER_SIZE and encode it as PNG. (TIFFRepresentation holds every size
        # of the icon at once, tens of megabytes that Pillow cannot read.)
        _send_size(image, _sel(b'setSize:'), _NSSize(RENDER_SIZE, RENDER_SIZE))
        cgimage = _send_cgimage(image, _sel(b'CGImageForProposedRect:context:hints:'), None, None, None)
        if not cgimage:
            return None
        bitmap = _send_id_id(_send_id(_NSBitmapImageRep, _sel(b'alloc')), _sel(b'initWithCGImage:'), cgimage)
        try:
            properties = _send_id(_NSDictionary, _sel(b'dictionary'))
            png = _send_representation(bitmap, _sel(b'representationUsingType:properties:'), NS_PNG, properties)
            if not png:
                return None
            data = ctypes.string_at(_send_id(png, _sel(b'bytes')), _send_ulong(png, _sel(b'length')))
        finally:
            _send_none(bitmap, _sel(b'release'))
    finally:
        _objc.objc_autoreleasePoolPop(pool)
    return Image.open(io.BytesIO(data)).convert('RGBA')
