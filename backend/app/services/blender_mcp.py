import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class BlenderMCPError(Exception):
    """Raised when BlenderMCP execution fails."""


class BlenderMCPClient:
    """HTTP client for the BlenderMCP (poly-mcp) server."""

    def __init__(self):
        self._timeout = httpx.Timeout(connect=5.0, read=180.0, write=10.0, pool=5.0)

    @property
    def base_url(self) -> str:
        return settings.blender_mcp_url.rstrip("/")

    async def health_check(self) -> bool:
        """Check if BlenderMCP server is reachable and responding."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(f"{self.base_url}/mcp/list_tools")
                return resp.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            logger.debug("BlenderMCP health check failed — server unreachable")
            return False
        except Exception:
            logger.exception("BlenderMCP health check unexpected error")
            return False

    async def execute_code(self, code: str) -> dict:
        """Execute a bpy Python script via BlenderMCP.

        Returns the tool invocation result dict.
        Raises BlenderMCPError on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/mcp/invoke/execute_blender_code",
                    json={"code": code},
                )
                resp.raise_for_status()
                data = resp.json()

                # Check for Blender-level errors in the response
                if isinstance(data, dict) and data.get("error"):
                    raise BlenderMCPError(f"Blender execution error: {data['error']}")

                return data

        except httpx.ConnectError:
            raise BlenderMCPError("BlenderMCP server is not reachable")
        except httpx.TimeoutException:
            raise BlenderMCPError("BlenderMCP execution timed out (180s)")
        except httpx.HTTPStatusError as e:
            raise BlenderMCPError(f"BlenderMCP HTTP error {e.response.status_code}: {e.response.text[:200]}")
        except BlenderMCPError:
            raise
        except Exception as e:
            raise BlenderMCPError(f"BlenderMCP unexpected error: {e}")


blender_mcp = BlenderMCPClient()
