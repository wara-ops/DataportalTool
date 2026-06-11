"""HTTP client (WCIBConnection) for the WARA-Ops dataportal API."""

import json
import logging
import os
from typing import Optional, Union

import requests
import xxhash

from . import utils
from . import wcib_format

_logger = logging.getLogger("toolslib.upload")


class WCIBError(Exception):
    """Raised when a dataportal API operation cannot be completed."""


class WCIBConnection:
    """
    A class to maintain the attributes for the HTTP requests


    Attributes
    ----------
    url : str
        Portal API URL
    token_file : str
        Filename holding the user token
    token_data : str
        User token
    timeout : int
        HTTP timeout

    Methods
    -------
    connect():
        Reads token and checks if API is available
    create_dataset(infofile, user, dryrun):
        Creates a new dataset
    upload(datasetid, src_list, data, prefix, dryrun):
        Upload files to dataset
    delete(datasetid, force, dryrun):
        Deletes a dataset
    list_datasets(dryrun):
        Lists user's datasets
    list_files(datasetid, fryrun):
        List files in dataset
    """

    def __init__(
        self, api_url: str, tokenfile: Optional[str] = "", token: Optional[str] = ""
    ):
        """
        Initiates object

        Parameters
        ----------

        Returns
        -------

        Raises
        ------
        """
        self.url = api_url
        self.token_file = tokenfile
        self.token_data = token
        self.timeout = (600, 1200)
        self._s = None

    def connect(self, session: Optional[object] = None) -> None:
        """
        Reads token and checks if API is available

        Parameters
        ----------

        Returns
        -------

        Raises
        ------
        Exception of token not provided or server cannot be connected
        """
        if (self.token_file == "") and (self.token_data == ""):
            raise WCIBError("No token provided")

        if self.token_data == "":
            with open(self.token_file, encoding="utf-8") as f:
                tok = f.read()
                self.token_data = tok.strip()

        self._s = requests.Session() if session is None else session

        response = self._s.get(f"{self.url}/test", timeout=self.timeout)
        if response.status_code >= 300:
            raise WCIBError("Failed to test api")

    def create_dataset(self, infofile: str, user: str, dryrun: bool) -> int:
        """
        Creates a new dataset

        Parameters
        ----------
        infofile : str
            File name containing MD info describing the dataset
        user : str
            Username, owner of the dataset
        dryrun : bool
            Indicate dryrun or not

        Returns
        -------
        0 : int
            Operation was ok
        1 : int
            Operation failed

        Raises
        ------
        Exception if info file is invalid
        """
        data = utils.parse_info(infofile)
        if not utils.validate_info(data):
            raise WCIBError("Invalid info file")

        # requets.post()

        # --data '{
        # "category": "metric",
        # "tenant": "tester",
        # "name": "'"${ARG1:-dataset1}"'",
        # "owner": "user01",
        # "short_info": "some short information",
        # "long_info": "dataset consiting of X. Gathered over Y in Z.",
        # "access_type": "'"${ARG2:-closed}"'",
        # "tags": ["tag1", "alsoatag"]
        # }'

        headers = {
            "content-type": "application/json",
            "Authorization": f"Bearer {self.token_data}",
        }

        pth = f"{self.url}/dataset"
        j = {}

        try:
            _data = {
                "category": data["category"],
                "tenant": data["tenant"],
                "name": data["dataset"],
                "owner": user,
                "short_info": data["short info"],
                "long_info": data["long info"],
                "access_type": data["access"],
                "tags": data["tags"],
            }

            if dryrun:
                _logger.info("Create dataset, %s", json.dumps(_data, indent=4))
            else:
                response = self._s.post(
                    pth, headers=headers, json=_data, timeout=self.timeout
                )
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("%s", self._error_detail(err))
            return 1

        wcib_format.print_created_dataset(j)

        return 0

    # parameters mirror the annotation request fields
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def set_file_metadata(
        self,
        datasetid: int,
        fileid: int,
        tags: Optional[list] = None,
        points_of_interest: Optional[list] = None,
        dryrun: bool = False,
    ) -> dict:
        """
        Sets (replaces) the user annotations on a single file.

        Updates ONLY the user-supplied annotations (tags and points of
        interest); it never touches file content. Works on any file row by
        FileID -- a datafile or an extrafile alike. The server rejects
        annotation on a non-READY file (HTTP 409).

        Parameters
        ----------
        datasetid : int
            Dataset ID
        fileid : int
            File ID (FileID) of the file to annotate
        tags : list[str] | None
            List of tag strings. Pass ``None`` to leave tags untouched; pass
            an empty list (``[]``) to clear all tags.
        points_of_interest : list[dict] | None
            List of points-of-interest time ranges, each a dict of the form
            ``{"start": ..., "stop": ..., "text": ...}``. Pass ``None`` to
            leave them untouched; pass an empty list to clear them. Items are
            passed through as-is (the server validates them).
        dryrun : bool
            Indicate dryrun or not

        Returns
        -------
        dict
            API response as JSON, or an empty dict when there is nothing to
            do (neither field provided) or on a dryrun.

        Raises
        ------
        requests.exceptions.HTTPError
            If the server returns an error status.
        """
        # Use ``is not None`` so an empty list (clear semantics) is honoured.
        body = {}
        if tags is not None:
            body["tags"] = tags
        if points_of_interest is not None:
            body["pointsOfInterest"] = points_of_interest

        if not body:
            _logger.debug(
                "set_file_metadata, datasetid %d, fileid %d, nothing to do",
                datasetid,
                fileid,
            )
            return {}

        headers = {"Authorization": f"Bearer {self.token_data}"}
        pth = f"{self.url}/dataset/{datasetid}/files/{fileid}"

        if dryrun:
            _logger.info(
                "set_file_metadata, datasetid %d, fileid %d, body %s",
                datasetid,
                fileid,
                body,
            )
            return {}

        response = self._s.put(pth, headers=headers, json=body, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _file_size_and_key(fname: str) -> tuple[int, str]:
        """
        Returns the file's byte size and an idempotency key.

        The key is the xxh128 hex digest of the file contents, streamed in
        1 MiB chunks so the file is never loaded fully into memory. The size
        is the on-disk byte count. Both are sent with atomic uploads so the
        server can validate the payload and de-duplicate retries.
        """
        size = os.path.getsize(fname)
        h = xxhash.xxh128()
        with open(fname, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return size, h.hexdigest()

    @staticmethod
    def _error_detail(err: Exception) -> str:
        """
        Render an exception for the user, including any server response body.

        A bare ``requests`` ``HTTPError`` stringifies to just the status line
        (e.g. "400 Client Error: ..."), hiding the API's explanation. When a
        response body is available, append it (trimmed) so the real reason --
        e.g. a field validation error -- is visible.
        """
        msg = str(err)
        response = getattr(err, "response", None)
        if response is not None:
            body = (response.text or "").strip()
            if body:
                msg = f"{msg} | server said: {body[:1000]}"
        return msg

    # parameters mirror set_file_metadata plus the upload response
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _annotate_uploaded(
        self,
        datasetid: int,
        resp_json: dict,
        tags: Optional[list],
        points_of_interest: Optional[list],
        dryrun: bool,
    ) -> None:
        """
        Annotates a freshly-uploaded file from its upload response.

        No-op when no annotations were requested or on a dryrun. Skips (with a
        warning) if the upload response does not report the file as READY,
        since the server rejects annotation of a non-READY file. Raises on a
        failed annotation request so the caller can record the partial state.
        """
        if (tags is None and points_of_interest is None) or dryrun:
            return

        fileid = resp_json.get("fileId", None)
        if fileid is None:
            return

        status = resp_json.get("status")
        if status is not None and status != "READY":
            _logger.warning(
                "Skipping annotation of file %s: not READY (status %s)",
                fileid,
                status,
            )
            return

        self.set_file_metadata(datasetid, fileid, tags, points_of_interest, dryrun)

    # locals mirror the upload request fields plus the deterministic file handle
    # pylint: disable=too-many-locals
    def _upload_extra(
        self, datasetid: int, fname: str, prefix: str, dryrun: bool
    ) -> dict:
        """
        Uploads an extra file, e.g., a file that does not fit the naming convention

        Parameters
        ----------
        datasetid : int
            Dataset ID
        fname : str
            Name of file to be uploaded
        prefix : str
            Prefix (subdir) of extrafiles
        dryrun : bool
            Indicate dryrun or not

        Returns
        -------
        j : dict
            API response as JSON

        Raises
        ------
        """
        headers = {
            "Authorization": f"Bearer {self.token_data}"
        }  # , "Content-Type": "multipart/form-data"}

        # prefix may be "dir", "dir/" or "dir/newname"
        body = {}
        sp = prefix.split("/")
        if len(sp) == 1:
            if sp[0]:
                body["prefix"] = sp[0]
            else:
                body["prefix"] = "extrafiles"

            body["filename"] = os.path.basename(fname)

        if len(sp) == 2:
            _prefix, _filename = sp
            if _prefix:
                body["prefix"] = _prefix
                if _filename:
                    body["filename"] = _filename
                else:
                    body["filename"] = os.path.basename(fname)
            else:
                if _filename:
                    body["prefix"] = _filename

        _logger.debug(
            "_upload_extra, datasetid %d, fname %s, prefix %s, body %s",
            datasetid,
            fname,
            prefix,
            body,
        )

        if len(body) != 2:
            _logger.info(
                "_upload_extra, datasetid %d, incomplete prefix and body %s",
                datasetid,
                body,
            )
            return {}

        pth = f"{self.url}/dataset/{datasetid}/extrafiles"

        j = {}

        if not dryrun:
            # Atomic streaming upload: send the exact byte size up front and an
            # Idempotency-Key (xxh128 hex of the bytes) so retries de-dup.
            size, idempotency_key = self._file_size_and_key(fname)
            body["size"] = size
            headers["Idempotency-Key"] = idempotency_key

            with open(fname, "rb") as data_fh:
                payload = (("data", data_fh),)
                response = self._s.post(
                    pth,
                    headers=headers,
                    data=body,
                    files=payload,
                    timeout=self.timeout,
                )
            response.raise_for_status()
            j = response.json()
            _logger.debug("response %s", json.dumps(j))
        else:
            _logger.info(
                "_upload_extra, datasetid %d, fname %s, body %s", datasetid, fname, body
            )

        return j

    # locals mirror the upload request fields plus the deterministic file handle
    # pylint: disable=too-many-locals
    def _upload_data(
        self, datasetid: int, fname: str, data: dict, dryrun: bool
    ) -> dict:
        """
        Uploads a data ("log" or "metric") file as a single atomic upload

        Parameters
        ----------
        datasetid : int
            Dataset ID
        fname : str
            Name of file to be uploaded
        data : dict
            Dict containing parsed filename
        dryrun : bool
            Indicate dryrun or not

        Returns
        -------
        j : dict
            API response as JSON

        Raises
        ------
        """
        _logger.debug("_upload_data filedata %s", json.dumps(data, indent=4))

        # Raises exception on int error
        data["count"] = int(data["count"])

        size, idempotency_key = self._file_size_and_key(fname)

        # The API validates start/stop as RFC3339 date-time (timezone required),
        # but filenames carry them without a zone, so normalize to the ...Z form.
        start_ok, start_norm = utils.normalize_timestamp(data["start"])
        stop_ok, stop_norm = utils.normalize_timestamp(data["stop"])
        start = start_norm if start_ok else data["start"]
        stop = stop_norm if stop_ok else data["stop"]

        form = {
            "start": start,
            "stop": stop,
            "count": int(data["count"]),
            "filename": os.path.basename(fname),
            "size": size,
        }

        uncompressedsize = data.get("size", "")
        if uncompressedsize != "":
            form["uncompressedsize"] = uncompressedsize

        dataflag = data.get("flag", "")
        if dataflag != "":
            form["dataflag"] = dataflag

        datatype = data.get("type", "")
        if datatype != "":
            form["datatype"] = datatype

        _logger.debug("_upload_data form %s", json.dumps(form, indent=4))

        if not dryrun:
            headers = {
                "Authorization": f"Bearer {self.token_data}",
                "Idempotency-Key": idempotency_key,
            }
            pth = f"{self.url}/dataset/{datasetid}/files"

            with open(fname, "rb") as data_fh:
                payload = (("data", (os.path.basename(fname), data_fh)),)
                response = self._s.post(
                    pth,
                    headers=headers,
                    data=form,
                    files=payload,
                    timeout=self.timeout,
                )
            response.raise_for_status()
            j = response.json()
            _logger.debug("response %s", json.dumps(j, indent=4))
        else:
            _logger.info("_upload_data %s", json.dumps(form, indent=4))

            j = {}

        return j

    # parameters mirror the upload request fields plus optional annotations
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def _upload_extra_files(
        self,
        datasetid: int,
        all_files: list[str],
        prefix: str,
        dryrun: bool,
        tags: Optional[list] = None,
        points_of_interest: Optional[list] = None,
    ) -> tuple[int, dict]:
        """
        Uploads an extra file

        Parameters
        ----------
        datasetid : int
            Dataset ID
        all_files : list[str]
            Name of file to be uploaded
        prefix : str
            Dest path and name of uploaded file, e.g. "subdir", "subdir/" and "subdir/newname"
        dryrun : bool
            Indicate dryrun or not
        tags : list[str] | None
            Tags applied to every freshly-uploaded file in the batch
        points_of_interest : list[dict] | None
            Points-of-interest applied to every freshly-uploaded file in the batch

        Returns
        -------
        ok, response : tuple[int, dict]

        Raises
        ------
        """
        ret = 0
        resp = {}

        for f in all_files:
            try:
                resp_json = self._upload_extra(datasetid, f, prefix, dryrun)

                _logger.debug("resp_json %s", str(resp_json))

                v = resp_json.get("path", None)
                if v is not None:
                    resp[f] = resp_json["path"]
            # pylint: disable=broad-exception-caught
            # per-file failures are logged and skipped so other files still upload
            except Exception as e:
                _logger.error("Upload of %s failed, %s", f, self._error_detail(e))
                ret = 1
                continue

            # Annotate the freshly-uploaded file. Reported separately so an
            # annotation failure is not misattributed to the upload.
            try:
                self._annotate_uploaded(
                    datasetid, resp_json, tags, points_of_interest, dryrun
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                _logger.error("Annotation of %s failed, %s", f, self._error_detail(e))
                ret = 1

        return ret, resp

    # parameters mirror the upload request fields
    # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
    # pylint: disable=too-many-branches
    def _upload_data_files(
        self,
        datasetid: int,
        all_files: list[str],
        data: dict,
        kind: str,
        dryrun: bool,
        tags: Optional[list] = None,
        points_of_interest: Optional[list] = None,
    ) -> tuple[int, dict]:
        """
        Uploads an extra file

        Parameters
        ----------
        datasetid : int
            Dataset ID
        all_files : list[str]
            Name of file to be uploaded
        data : dict
            Dict of naming convention fields
        kind : str
            "log" or "metric"
        dryrun : bool
            Indicate dryrun or not
        tags : list[str] | None
            Tags applied to every freshly-uploaded file in the batch
        points_of_interest : list[dict] | None
            Points-of-interest applied to every freshly-uploaded file in the batch

        Returns
        -------
        ok, response : tuple[int, dict]

        Raises
        ------
        """
        ret = 0  # ok
        resp = {}

        send_d = {}

        # is a single file is uploaded, its name may be constructed from user params
        if len(all_files) == 1:
            f = all_files[0]
            src_file = os.path.basename(f)

            ok, long_name = utils.create_filename(data, src_file, kind)

            _logger.debug("ok %s, long_name %s", ok, long_name)

            if ok:
                # Ensure parameters make sense.
                kind, filedata = utils.parse_filename(long_name)
            else:
                kind, filedata = utils.parse_filename(src_file)

            _logger.debug("src_file %s, kind %s, filedata %s", src_file, kind, filedata)

            # We expect kind it to be either "log" or "metric"

            if kind != "extra":
                send_d[f] = filedata
            else:
                # If name cannot be properly parsed, it will be marked as "extra". Bad name!
                ret = 1

        # All filenames must follow naming convention
        if len(all_files) > 1:
            for f in all_files:
                src_file = os.path.basename(f)
                kind, filedata = utils.parse_filename(src_file)

                _logger.debug(
                    "src_file %s, kind %s, filedata %s", src_file, kind, filedata
                )

                if kind != "extra":
                    send_d[f] = filedata
                else:
                    ret = 1

        _logger.debug("send_d %s", json.dumps(send_d))

        # Here, send_d contains valid file names and filedata
        for fname, filedata in send_d.items():
            try:
                resp_json = self._upload_data(datasetid, fname, filedata, dryrun)

                _logger.debug("resp_json %s", str(resp_json))

                v = resp_json.get("path", None)
                if v is not None:
                    resp[fname] = resp_json["path"]
            # pylint: disable=broad-exception-caught
            # per-file failures are logged and skipped so other files still upload
            except Exception as e:
                _logger.error("Upload of %s failed, %s", fname, self._error_detail(e))
                ret = 1
                continue

            # Annotate the freshly-uploaded file. Reported separately so an
            # annotation failure is not misattributed to the upload.
            try:
                self._annotate_uploaded(
                    datasetid, resp_json, tags, points_of_interest, dryrun
                )
            except Exception as e:  # pylint: disable=broad-exception-caught
                _logger.error(
                    "Annotation of %s failed, %s", fname, self._error_detail(e)
                )
                ret = 1

        return ret, resp

    def _list_files(
        self, datasetid: int, extrafiles: bool, dryrun: bool, limit: int = 0
    ) -> Union[list[dict], None]:
        """ """
        headers = {"Authorization": f"Bearer {self.token_data}"}

        files = []
        _extra = "true" if extrafiles else "false"

        pth = f"{self.url}/dataset/{datasetid}/files?limit={limit}&extrafiles={_extra}"

        j = {}

        try:
            if dryrun:
                _logger.info("List files in dataset %d", datasetid)
            else:
                response = self._s.get(pth, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("list files failed, %s", self._error_detail(err))
            return None

        _logger.debug(json.dumps(j, indent=3))

        _files = j.get("data", [])
        files.extend(_files)

        return files

    # parameters mirror the upload request fields
    # pylint: disable=too-many-arguments,too-many-positional-arguments
    def upload(
        self,
        datasetid: int,
        src_list: list[str],
        data: dict,
        prefix: str,
        kind: str,
        dryrun: bool,
        tags: Optional[list] = None,
        points_of_interest: Optional[list] = None,
    ) -> int:
        """
        Uploads a file to a dataset

        Parameters
        ----------
        datasetid : int
            Dataset ID
        src_list : list[str]
            List of name of files to be uploaded
        data : dict | None
                Dict (API) describing the file
                {   "datatype": str,
                    "dataflag": str,
                    "start": str,
                    "stop": str,
                    "count": int,
                    "size": int | str,
                }
        prefix : str
            Prefix (upload dir) for extrafiles. If set, file is assumed to be an
            extrafile regardless of naming or parameters.
        kind : str
            Either "log" or "metric"
        dryrun : bool
            Indicate dryrun or not
        tags : list[str] | None
            Optional tags to apply to every freshly-uploaded file in the
            batch (datafiles and extrafiles alike). ``None`` leaves tags
            untouched; an empty list clears them.
        points_of_interest : list[dict] | None
            Optional points-of-interest time ranges
            (``{"start", "stop", "text"}``) to apply to every freshly-uploaded
            file in the batch. ``None`` leaves them untouched.

        Returns
        -------
        int
            0, Operation was ok,
            1, Operation was not ok

        Raises
        ------
        """
        _all_files = utils.get_all_src_files(src_list)
        _logger.debug("src_list %s, all_files %s", src_list, _all_files)

        # Make sure it is a file
        all_files = list(filter(os.path.isfile, _all_files))

        if len(all_files) == 0:
            _logger.info("No files found")
            return 1

        # Extrafiles are uploaded "as is"
        if prefix != "":
            ok, resp = self._upload_extra_files(
                datasetid, all_files, prefix, dryrun, tags, points_of_interest
            )
        else:
            ok, resp = self._upload_data_files(
                datasetid, all_files, data, kind, dryrun, tags, points_of_interest
            )

        fmt = "{:<50} | {:<50}"
        print(fmt.format("Source", "Dest"))
        print("-" * 51 + "+" + "-" * 61)
        for src, dst in resp.items():
            print(fmt.format(src, dst))

        return ok

    def delete(self, datasetid: int, force: bool, dryrun: bool) -> int:
        """
        Deletes a dataset

        Parameters
        ----------
        datasetid : int
            Dataset ID
        force : bool
            Indicate to delete even if dataset is nonempty
        dryrun : bool
            Indicate dryrun or not

        Returns
        -------
        int
            0, Operation was ok,
            1, Operation was not ok

        Raises
        ------
        """
        headers = {"Authorization": f"Bearer {self.token_data}"}

        pth = f"{self.url}/dataset/{datasetid}"

        # Unless force, we will not remove non-empty datasets
        if not force:
            data_files = self._list_files(datasetid, False, dryrun, limit=1)
            if data_files is None:
                _logger.error("Failed to retrieve data files")
                return 1

            if len(data_files) > 0:
                _logger.error("Dataset is not empty, data files exists")
                return 1

            extra_files = self._list_files(datasetid, True, dryrun, limit=1)
            if extra_files is None:
                _logger.error("Failed to retrieve extra files")
                return 1

            if len(extra_files) > 0:
                _logger.error("Dataset is not empty, extra files exists")
                return 1

        j = {}
        try:
            if dryrun:
                _logger.info("delete file, %s", str(pth))
            else:
                response = self._s.delete(pth, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("delete failed, %s", self._error_detail(err))
            return 1

        _logger.debug("response %s", json.dumps(j, indent=4))

        return 0

    def list_datasets(self, dryrun: bool) -> int:
        """
        Lists user's all datasets

        Parameters
        ----------
        dryrun : bool
            Indicate dryrun or not

        Returns
        -------
        int
            0, Operation was ok,
            1, Operation was not ok

        Raises
        ------
        """
        # headers = {"content-type": "application/json", "Authorization": self.token_data }
        headers = {"Authorization": f"Bearer {self.token_data}"}

        # print(headers)

        pth = f"{self.url}/dataset"

        j = {}

        try:
            if dryrun:
                _logger.info("List datasets")
            else:
                response = self._s.get(pth, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("list datasets failed, %s", self._error_detail(err))
            return 1

        datasets = j.get("Datasets", [])

        wcib_format.print_datasets(datasets)

        return 0

    def list_files(self, datasetid: int, dryrun: bool) -> int:
        """
        Lists files in named dataset

        Parameters
        ----------
        dryrun : bool
            Indicate dryrun or not

        Returns
        -------
        int
            0, Operation was ok,
            1, Operation was not ok

        Raises
        ------
        """
        data_files = self._list_files(datasetid, False, dryrun)
        if data_files is None:
            return 1

        extra_files = self._list_files(datasetid, True, dryrun)
        if extra_files is None:
            return 1

        wcib_format.print_files([data_files, extra_files])

        return 0
