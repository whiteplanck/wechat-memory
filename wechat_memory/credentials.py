"""Optional current-user Windows DPAPI storage, separate from chat archives."""
import ctypes
import os
from pathlib import Path
import re
import sys
import tempfile
from threading import RLock


def validate_key(key):
    if not isinstance(key, str) or not re.fullmatch(r"[!-~]{8,512}", key):
        raise ValueError("请填写有效 API Key，不包含空格或换行")
    return key


def dpapi(data, decrypt=False):
    if sys.platform != "win32":
        raise ValueError("加密记住 Key 仅支持 Windows；当前平台仍可使用临时 Key")
    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint32), ("data", ctypes.c_void_p)]
    buffer = ctypes.create_string_buffer(data)
    source, result = Blob(len(data), ctypes.cast(buffer, ctypes.c_void_p)), Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(Blob)]
    function.restype = ctypes.c_int
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        # UI_FORBIDDEN only: never LOCAL_MACHINE, so protection is user-scoped.
        if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
            raise ValueError("Windows 无法处理已保存凭据，请在原 Windows 账户下重试或重新保存 Key")
        return ctypes.string_at(result.data, result.size)
    finally:
        ctypes.memset(buffer, 0, len(buffer))
        if result.data:
            ctypes.memset(result.data, 0, result.size)
            kernel.LocalFree(result.data)


class CredentialStore:
    def __init__(self, directory=None):
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "WeChatMemory" / "credentials"
        self.path = Path(directory or base) / "deepseek.dpapi"
        self.lock = RLock()

    def status(self):
        return {"supported": sys.platform == "win32", "saved": self.path.is_file()}

    def save(self, key):
        encrypted = dpapi(validate_key(key).encode("ascii"))
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, delete=False) as handle:
                    temporary = Path(handle.name)
                    handle.write(encrypted)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()
        return self.status()

    def load(self):
        with self.lock:
            try:
                if self.path.stat().st_size > 16384:
                    raise ValueError("凭据文件异常，请删除后重新保存 Key")
                encrypted = self.path.read_bytes()
            except FileNotFoundError:
                raise ValueError("尚未保存 Key，请先填写并保存") from None
            try:
                return validate_key(dpapi(encrypted, decrypt=True).decode("ascii"))
            except (UnicodeError, ValueError):
                raise ValueError("无法解密已保存 Key，请在原 Windows 账户下重试或重新保存") from None

    def delete(self):
        with self.lock:
            self.path.unlink(missing_ok=True)
        return self.status()
