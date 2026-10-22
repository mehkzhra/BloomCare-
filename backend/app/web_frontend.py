"""Optional same-origin Vite frontend for a single hosted Python web service."""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class SPAFiles(StaticFiles):
    async def get_response(self, path, scope):
        # StaticFiles.get_path uses backslashes on Windows; URL checks need slashes.
        path = path.replace("\\", "/")
        # Unknown API calls must stay API errors, never a successful HTML page.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            # Assets and attempted filesystem paths must not fall back to index.
            if error.status_code != 404 or any("." in p for p in Path(path).parts):
                raise
            return await super().get_response("index.html", scope)


def mount_frontend(app, directory):
    path = Path(directory).resolve()
    if not (path / "index.html").is_file():
        raise ValueError("The configured frontend build is missing")
    app.mount("/", SPAFiles(directory=str(path)), name="frontend")
