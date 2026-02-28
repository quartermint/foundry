import ftplib
import logging
import ssl
from pathlib import Path

logger = logging.getLogger(__name__)


class _ImplicitFTP_TLS(ftplib.FTP_TLS):
    """FTP_TLS subclass that wraps the socket immediately for implicit TLS (port 990)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def connect(self, host="", port=0, timeout=-999, source_address=None):
        if host:
            self.host = host
        if port:
            self.port = port
        if timeout != -999:
            self.timeout = timeout
        if source_address is not None:
            self.source_address = source_address

        import socket

        self.sock = socket.create_connection(
            (self.host, self.port), self.timeout, source_address=self.source_address
        )
        self.af = self.sock.family
        # Immediately wrap the socket with TLS for implicit FTPS
        self.sock = self.context.wrap_socket(self.sock, server_hostname=self.host)
        self.file = self.sock.makefile("r")
        self.welcome = self.getresp()
        return self.welcome


async def upload_file(
    ip: str, access_code: str, local_path: str, remote_filename: str
) -> bool:
    """Upload a file to the Bambu printer via implicit FTPS on port 990."""
    try:
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        ftp = _ImplicitFTP_TLS(context=ssl_ctx)
        ftp.connect(host=ip, port=990, timeout=30)
        ftp.login(user="bblp", passwd=access_code)

        # Enable data channel encryption
        ftp.prot_p()

        local = Path(local_path)
        with open(local, "rb") as f:
            ftp.storbinary(f"STOR {remote_filename}", f)

        ftp.quit()
        logger.info("FTPS upload succeeded: %s -> %s on %s", local_path, remote_filename, ip)
        return True

    except Exception:
        logger.exception("FTPS upload failed: %s -> %s on %s", local_path, remote_filename, ip)
        return False
