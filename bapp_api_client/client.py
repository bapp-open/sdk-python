"""BAPP Auto API Client for Python."""

import io
import time
import requests


def _has_files(data):
    """Return True if data dict contains file-like values."""
    if not isinstance(data, dict):
        return False
    for v in data.values():
        if isinstance(v, (io.IOBase, bytes, bytearray)):
            return True
        if hasattr(v, "read"):
            return True
        if isinstance(v, tuple) and len(v) >= 2:
            return True
    return False


class PagedList(list):
    """A list of results with pagination metadata.

    Behaves like a normal list (iterating, indexing, len) but also exposes
    ``count``, ``next``, and ``previous`` from the paginated API response.
    """

    def __init__(self, results, *, count=0, next=None, previous=None):
        super().__init__(results)
        self.count = count
        self.next = next
        self.previous = previous

    def __repr__(self):
        return f"PagedList(count={self.count}, len={len(self)})"


class BappApiClient:
    """Client for the BAPP Auto API.

    Args:
        bearer: Bearer token for authentication.
        token: Token-based authentication (``Token <value>``).
        host: Base URL of the API.
        tenant: Default tenant ID sent as ``x-tenant-id`` header.
        app: Default app slug sent as ``x-app-slug`` header.
    """

    def __init__(
        self,
        bearer=None,
        token=None,
        host="https://panel.bapp.ro/api",
        tenant=None,
        app="account",
    ):
        self.host = host.rstrip("/")
        self.tenant = tenant
        self.app = app
        self._session = requests.Session()
        if bearer:
            self._session.headers["Authorization"] = f"Bearer {bearer}"
        elif token:
            self._session.headers["Authorization"] = f"Token {token}"

    # -- internals -----------------------------------------------------------

    def _headers(self, extra=None):
        h = {}
        if self.tenant is not None:
            h["x-tenant-id"] = str(self.tenant)
        if self.app is not None:
            h["x-app-slug"] = self.app
        if extra:
            h.update(extra)
        return h

    def _request(self, method, path, params=None, json=None, headers=None):
        kwargs = {}
        if json is not None and _has_files(json):
            files = {}
            data = {}
            for k, v in json.items():
                if isinstance(v, (io.IOBase, bytes, bytearray)) or hasattr(v, "read"):
                    files[k] = v
                elif isinstance(v, tuple) and len(v) >= 2:
                    files[k] = v
                else:
                    data[k] = v
            kwargs["files"] = files
            kwargs["data"] = data
        else:
            kwargs["json"] = json
        resp = self._session.request(
            method,
            f"{self.host}{path}",
            params=params,
            headers=self._headers(headers),
            **kwargs,
        )
        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()

    # -- user ----------------------------------------------------------------

    def me(self):
        """Get current user profile."""
        return self._request("GET", "/tasks/bapp_framework.me", headers={"x-app-slug": ""})

    # -- app -----------------------------------------------------------------

    def get_app(self, app_slug):
        """Get app configuration by slug."""
        return self._request(
            "GET", "/tasks/bapp_framework.getapp", headers={"x-app-slug": app_slug}
        )

    # -- entity introspect ---------------------------------------------------

    def list_introspect(self, content_type):
        """Get entity list introspect for a content type."""
        return self._request(
            "GET", "/tasks/bapp_framework.listintrospect", params={"ct": content_type}
        )

    def detail_introspect(self, content_type, pk=None):
        """Get entity detail introspect for a content type."""
        params = {"ct": content_type}
        if pk is not None:
            params["pk"] = pk
        return self._request(
            "GET", "/tasks/bapp_framework.detailintrospect", params=params
        )

    # -- entity CRUD ---------------------------------------------------------

    def list(self, content_type, **filters):
        """List entities of a content type with optional filters.

        Returns a ``PagedList`` — a regular list of results with additional
        ``.count``, ``.next``, and ``.previous`` attributes.
        """
        data = self._request(
            "GET", f"/content-type/{content_type}/", params=filters or None
        )
        return PagedList(
            data.get("results", []),
            count=data.get("count", 0),
            next=data.get("next"),
            previous=data.get("previous"),
        )

    def get(self, content_type, id):
        """Get a single entity by content type and ID."""
        return self._request("GET", f"/content-type/{content_type}/{id}/")

    def create(self, content_type, data=None):
        """Create a new entity of a content type."""
        return self._request("POST", f"/content-type/{content_type}/", json=data)

    def update(self, content_type, id, data=None):
        """Full update of an entity."""
        return self._request("PUT", f"/content-type/{content_type}/{id}/", json=data)

    def patch(self, content_type, id, data=None):
        """Partial update of an entity."""
        return self._request("PATCH", f"/content-type/{content_type}/{id}/", json=data)

    def delete(self, content_type, id):
        """Delete an entity."""
        return self._request("DELETE", f"/content-type/{content_type}/{id}/")

    # -- document views ------------------------------------------------------

    def get_document_views(self, record):
        """Extract available document views from a record.

        Works with both ``public_view`` (new) and ``view_token`` (legacy)
        formats.  Returns a list of dicts with keys: ``label``, ``token``,
        ``type`` (``"public_view"`` or ``"view_token"``), ``variations``,
        and ``default_variation``.
        """
        views = []
        for entry in (record.get("public_view") or []):
            views.append({
                "label": entry.get("label", ""),
                "token": entry.get("view_token", ""),
                "type": "public_view",
                "variations": entry.get("variations"),
                "default_variation": entry.get("default_variation"),
            })
        for entry in (record.get("view_token") or []):
            views.append({
                "label": entry.get("label", ""),
                "token": entry.get("view_token", ""),
                "type": "view_token",
                "variations": None,
                "default_variation": None,
            })
        return views

    def get_document_url(self, record, output="html", label=None,
                         variation=None, download=False):
        """Build a document render/download URL from a record.

        Works with both ``public_view`` and ``view_token`` formats.
        Prefers ``public_view`` when both are present on a record.

        Args:
            record: Entity dict from :meth:`list` or :meth:`get`.
            output: Desired format — ``"html"``, ``"pdf"``, ``"jpg"``, or
                ``"context"``.
            label: Select a specific view by label (first match wins).
                When *None* the first available view is used.
            variation: Variation code for ``public_view`` entries that
                support variations (e.g. ``"v4"``).  Falls back to the
                entry's ``default_variation`` when *None*.
            download: When *True* the response is sent as an attachment
                (``Content-Disposition: attachment``).  For ``public_view``
                this appends ``&download=true``; for legacy ``view_token``
                with ``output="pdf"`` this selects ``pdf.download`` instead
                of ``pdf.view``.

        Returns:
            URL string, or *None* if the record has no view tokens.
        """
        views = self.get_document_views(record)
        if not views:
            return None

        view = None
        if label is not None:
            for v in views:
                if v["label"] == label:
                    view = v
                    break
        if view is None:
            view = views[0]

        token = view["token"]
        if not token:
            return None

        if view["type"] == "public_view":
            url = f"{self.host}/render/{token}?output={output}"
            v = variation or view.get("default_variation")
            if v:
                url += f"&variation={v}"
            if download:
                url += "&download=true"
            return url

        # Legacy view_token
        if output == "pdf":
            action = "pdf.download" if download else "pdf.view"
        elif output == "context":
            action = "pdf.context"
        else:
            action = "pdf.preview"
        return f"{self.host}/documents/{action}?token={token}"

    def get_document_content(self, record, output="html", label=None,
                             variation=None, download=False):
        """Fetch document content (PDF, HTML, JPG, etc.) as bytes.

        Builds the URL via :meth:`get_document_url` and fetches the raw
        content.  The token embedded in the URL provides authentication.

        Args:
            record: Entity dict from :meth:`list` or :meth:`get`.
            output: Desired format — ``"html"``, ``"pdf"``, ``"jpg"``, or
                ``"context"``.
            label: Select a specific view by label.
            variation: Variation code for ``public_view`` entries.
            download: When *True* the server sends the response as an
                attachment.

        Returns:
            ``bytes`` content, or *None* if the record has no view tokens.

        Raises:
            requests.HTTPError: On non-2xx responses.
        """
        url = self.get_document_url(
            record, output=output, label=label, variation=variation,
            download=download,
        )
        if url is None:
            return None
        resp = self._session.get(url)
        resp.raise_for_status()
        return resp.content

    # -- tasks ---------------------------------------------------------------

    def list_tasks(self):
        """List all available task codes."""
        return self._request("GET", "/tasks")

    def detail_task(self, code):
        """Get task configuration by code."""
        return self._request("OPTIONS", f"/tasks/{code}")

    def run_task(self, code, payload=None):
        """Run a task. Uses GET when no payload, POST otherwise."""
        if payload is None:
            return self._request("GET", f"/tasks/{code}")
        return self._request("POST", f"/tasks/{code}", json=payload)

    def run_task_async(self, code, payload=None, poll_interval=1, timeout=300):
        """Run a long-running task and poll until finished.

        When the task returns an ``id``, the method polls
        ``bapp_framework.taskdata`` until the task finishes (or fails).
        Returns the final task data dict which includes ``file`` when
        the task produces a downloadable file.

        Args:
            code: Task code.
            payload: Task payload (triggers POST).
            poll_interval: Seconds between polls (default 1).
            timeout: Max seconds to wait (default 300).

        Raises:
            TimeoutError: If the task doesn't finish within *timeout*.
            RuntimeError: If the task reports failure.
        """
        result = self.run_task(code, payload)
        task_id = result.get("id") if isinstance(result, dict) else None
        if task_id is None:
            return result

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            page = self._request(
                "GET", "/content-type/bapp_framework.taskdata/",
                params={"id": task_id},
            )
            results = page.get("results", [])
            if not results:
                continue
            task_data = results[0]
            if task_data.get("failed"):
                raise RuntimeError(
                    f"Task {code} failed: {task_data.get('message', '')}"
                )
            if task_data.get("finished"):
                return task_data
        raise TimeoutError(f"Task {code} ({task_id}) did not finish within {timeout}s")
