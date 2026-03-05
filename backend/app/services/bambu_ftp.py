import ftplib
import io
import logging
import socket
import ssl
from pathlib import Path

logger = logging.getLogger(__name__)


class _ImplicitFTP_TLS(ftplib.FTP_TLS):
    """FTP_TLS subclass for Bambu Lab printers.

    Handles two Bambu-specific requirements:
    1. Implicit TLS (socket wrapped immediately on connect, port 990)
    2. TLS session reuse on data channels (printer returns 522 without it)
    """

    def connect(self, host="", port=0, timeout=-999, source_address=None):
        if host:
            self.host = host
        if port:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        if source_address is not None:
            self.source_address = source_address

        self.sock = socket.create_connection(
            (self.host, self.port), self.timeout,
            source_address=getattr(self, "source_address", None),
        )
        self.af = self.sock.family
        # Immediately wrap the socket with TLS for implicit FTPS
        self.sock = self.context.wrap_socket(self.sock, server_hostname=self.host)
        self.file = self.sock.makefile("r")
        self.welcome = self.getresp()
        return self.welcome

    def ntransfercmd(self, cmd, rest=None):
        """Override to reuse the control channel's TLS session on data channels.

        Bambu printers require TLS session reuse (RFC 4217) and reject data
        connections with '522 SSL connection failed: session reuse required'
        without it.
        """
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(
                conn,
                server_hostname=self.host,
                session=self.sock.session,  # reuse control channel session
            )
        return conn, size


def _make_ftp_connection(ip: str, access_code: str) -> _ImplicitFTP_TLS:
    """Create and authenticate an implicit FTPS connection to a Bambu printer."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    ftp = _ImplicitFTP_TLS(context=ssl_ctx)
    ftp.connect(host=ip, port=990, timeout=30)
    ftp.login(user="bblp", passwd=access_code)
    ftp.prot_p()
    return ftp


async def diagnose_ftp(ip: str, access_code: str) -> dict:
    """Probe a Bambu printer's FTP to discover writable storage paths.

    Returns {"directories": [...], "writable_paths": [...], "errors": {...}}.
    """
    TEST_FILE = ".foundry_probe"
    TEST_DATA = b"probe"
    candidate_paths = ["/", "/sdcard/", "/udisk/", "/cache/"]
    directories: list[str] = []
    writable_paths: list[str] = []
    errors: dict[str, str] = {}

    try:
        ftp = _make_ftp_connection(ip, access_code)

        # List root directories
        try:
            entries = ftp.nlst("/")
            directories = [e if e.startswith("/") else f"/{e}" for e in entries]
        except Exception as exc:
            errors["nlst"] = str(exc)

        # Add any discovered directories as candidates
        for d in directories:
            path = d.rstrip("/") + "/"
            if path not in candidate_paths:
                candidate_paths.append(path)

        # Probe each candidate for writability
        for path in candidate_paths:
            remote = f"{path.rstrip('/')}/{TEST_FILE}" if path != "/" else f"/{TEST_FILE}"
            try:
                ftp.storbinary(f"STOR {remote}", io.BytesIO(TEST_DATA))
                writable_paths.append(path)
                # Clean up
                try:
                    ftp.delete(remote)
                except Exception:
                    pass
            except Exception as exc:
                errors[path] = str(exc)

        ftp.quit()
    except Exception as exc:
        errors["connection"] = str(exc)

    return {
        "directories": directories,
        "writable_paths": writable_paths,
        "errors": errors,
    }


async def upload_file(
    ip: str, access_code: str, local_path: str, remote_filename: str,
    storage_path: str | None = None,
) -> str | None:
    """Upload a file to the Bambu printer via implicit FTPS on port 990.

    Returns the remote path on success (e.g. '/sdcard/file.3mf'), None on failure.
    The returned path should be used in the MQTT ftp:// URL.

    If storage_path is provided, uploads directly there (skip probing).
    Otherwise tries: / -> /sdcard/ -> /udisk/ -> /cache/
    """
    try:
        ftp = _make_ftp_connection(ip, access_code)

        local = Path(local_path)

        if storage_path:
            # Use configured path directly
            remote_path = f"{storage_path.rstrip('/')}/{remote_filename}"
            with open(local, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)
        else:
            # Probe paths in priority order
            probe_paths = ["/", "/sdcard/", "/udisk/", "/cache/"]
            remote_path = None
            with open(local, "rb") as f:
                for base in probe_paths:
                    candidate = f"{base.rstrip('/')}/{remote_filename}" if base != "/" else f"/{remote_filename}"
                    try:
                        f.seek(0)
                        ftp.storbinary(f"STOR {candidate}", f)
                        remote_path = candidate
                        break
                    except Exception:
                        logger.info("STOR %s failed, trying next path", candidate)
                        continue

            if not remote_path:
                logger.error("All FTP upload paths failed for %s on %s", remote_filename, ip)
                ftp.quit()
                return None

        ftp.quit()
        logger.info("FTPS upload succeeded: %s -> %s on %s", local_path, remote_path, ip)
        return remote_path

    except Exception:
        logger.exception("FTPS upload failed: %s -> %s on %s", local_path, remote_filename, ip)
        return None
