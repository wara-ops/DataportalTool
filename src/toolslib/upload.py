import os
import json
import logging
from typing import Optional

import requests

from . import utils

# Set default level
logging.basicConfig(level=logging.WARN)
_logger = logging.getLogger('toolslib.upload')
_logger.setLevel(logging.DEBUG)
logging.VERBOSE = 5
logging.addLevelName(logging.VERBOSE, "VERBOSE")

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
    delete(datasetid, dryrun):
        Deletes a dataset
    list_datasets(dryrun):
        Lists user's datasets
    list_files(datasetid, fryrun):
        List files in dataset
    """
    def __init__(self, api_url : str, tokenfile : Optional[str] = "", token : Optional[str] = ""):
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
        self.timeout = (10, 120)
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
            raise Exception("No token provided")

        if self.token_data == "":
            with open(self.token_file, mode='r') as f:
                tok = f.read()
                self.token_data = tok.strip()

        self._s = requests.Session()
        response = self._s.get(f'{self.url}/test', timeout=self.timeout)
        if response.status_code >= 300:
            raise Exception("Failed to test api")


    def create_dataset(self, infofile : str, user : str, dryrun : bool) -> int:
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
            raise Exception("Invalid info file")

        # requets.post()

        #--data '{
        #"category": "metric",
        #"tenant": "tester",
        #"name": "'"${ARG1:-dataset1}"'",
        #"owner": "user01",
        #"short_info": "some short information",
        #"long_info": "dataset consiting of X. Gathered over Y in Z.",
        #"access_type": "'"${ARG2:-closed}"'",
        #"tags": ["tag1", "alsoatag"]
        #}'


        headers = {"content-type": "application/json", "Authorization": f"Bearer {self.token_data}" }

        pth = f'{self.url}/dataset'
        j = {}

        try:
            _data = {"category": data["category"],
                 "tenant": data["tenant"],
                 "name": data["dataset"],
                 "owner": user,
                 "short_info": data["short info"],
                 "long_info": data["long info"],
                 "access_type": data["access"],
                 "tags": data["tags"]
                 }

            if dryrun:
                _logger.info("Create dataset, %s", json.dumps(_data, indent=4))
            else:
                response = self._s.post(pth, headers=headers, json=_data, timeout=self.timeout)
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("%s", str(err))
            return 1


        fmt = "{:>9} | {:<40}"
        print(fmt.format("DatasetID", "ContainerName"))
        print("----------+--------------------------------------------------------------------------------------------------")
        print(fmt.format(j.get("DatasetID", "-"), j.get("ContainerName", "-")))

        return 0


    def _upload_extra(self, datasetid : int, fname : str, prefix : str, dryrun: bool) -> dict:
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
        headers = {"Authorization": f"Bearer {self.token_data}"}  # , "Content-Type": "multipart/form-data"}

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

        _logger.debug("_upload_extra, datasetid %d, fname %s, prefix %s, body %s", datasetid, fname, prefix, body)

        if len(body) != 2:
            _logger.info("_upload_extra, datasetid %d, incomplete prefix and body %s", datasetid, body)
            return {}

        pth = f'{self.url}/dataset/{datasetid}/extrafiles'
        # payload = (('data', open(fname, 'rb')), ('prefix', prefix), ('filename', os.path.basename(fname)))
        payload = (('data', open(fname, 'rb')),)

        j = {}

        if not dryrun:
            response = self._s.put(pth, headers=headers, data=body, files=payload, timeout=self.timeout)
            response.raise_for_status()
            j = response.json()
            _logger.debug("response %s", json.dumps(j))
        else:
            _logger.info("_upload_extra, datasetid %d, fname %s, body %s", datasetid, fname, body)

        return j


    def _upload_data(self, datasetid: int, fname: str, data: dict, dryrun: bool) -> dict:
        """
        Uploads a data ("log" or "metric") file

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

        req_body = {"start": data["start"], "stop": data["stop"], "count": int(data["count"])}

        size = data.get("size", "")
        if size != "":
            req_body["uncompressedsize"] = size

        dataflag = data.get("flag", "")
        if dataflag != "":
            req_body["dataflag"] = dataflag

        datatype = data.get("type", "")
        if datatype != "":
            req_body["datatype"] = datatype

        _logger.debug("_upload_data req_body %s", json.dumps(req_body, indent=4))

        headers = {"content-type": "application/json", "Authorization": f"Bearer {self.token_data}" }
        pth = f'{self.url}/dataset/{datasetid}/files'

        if not dryrun:
            response = self._s.post(pth, headers=headers, json=req_body, timeout=self.timeout)
            response.raise_for_status()
            j = response.json()
            _logger.debug("response %s", json.dumps(j, indent=4))

            datafileid = j.get("fileId", -1)
            if datafileid < 0:
                raise Exception(f'Failed to prepare file structures for {fname}')

            headers = {"Authorization": f"Bearer {self.token_data}" }
            pth = f'{self.url}/dataset/{datasetid}/files/{datafileid}'
            payload = (('data', (os.path.basename(fname), open(fname, 'rb'))),)

            response = self._s.put(pth, headers=headers, files=payload, timeout=self.timeout)
            response.raise_for_status()
            j = response.json()
            _logger.debug("json response %s", json.dumps(j, indent=4))
        else:
            _logger.info("_upload_data %s", json.dumps(req_body, indent=4))

            j = {}

        return j


    def _upload_extra_files(self, datasetid : int, all_files : list[str], prefix : str, dryrun : bool) -> tuple[int, dict]:
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
            except Exception as e:
                _logger.error("Upload of %s failed, %s", f, str(e))
                ret = 1

        return ret, resp


    def _upload_data_files(self, datasetid : int, all_files : list[str], data : dict, kind : str, dryrun : bool) -> tuple[int, dict]:
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

        Returns
        -------
        ok, response : tuple[int, dict]

        Raises
        ------
        """
        ret = 0     # ok
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

                _logger.debug("src_file %s, kind %s, filedata %s", src_file, kind, filedata)

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
            except Exception as e:
                _logger.error("Upload of %s failed, %s", fname, str(e))
                ret = 1

        return ret, resp


    def upload(self, datasetid : int, src_list : list[str], data : dict | None, prefix : str, kind : str, dryrun : bool) -> int:
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
            Prefix (upload dir) for extrafiles. If set, file as assumed to be extrafile regardless of naming or parameters.
        kind : str
            Either "log" or "metric"
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
        _all_files = utils.get_all_src_files(src_list)
        _logger.debug("src_list %s, all_files %s", src_list, _all_files)

        # Make sure it is a file
        all_files = list(filter(os.path.isfile, _all_files))

        if len(all_files) == 0:
            _logger.info("No files found")
            return 1

        # Extrafiles are uploaded "as is"
        if prefix != "":
            ok, resp = self._upload_extra_files(datasetid, all_files, prefix, dryrun)
        else:
            ok, resp = self._upload_data_files(datasetid, all_files, data, kind, dryrun)

        fmt = "{:<50} | {:<50}"
        print(fmt.format("Source", "Dest"))
        print("---------------------------------------------------+-------------------------------------------------------------")
        for src, dst in resp.items():
            print(fmt.format(src, dst))

        return ok


    def delete(self, datasetid : int, dryrun : bool) -> int:
        """
        Deletes a dataset

        Parameters
        ----------
        datasetid : int
            Dataset ID
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
        headers = {"Authorization": f"Bearer {self.token_data}" }

        pth = f'{self.url}/dataset/{datasetid}'

        j = {}
        try:
            if dryrun:
                _logger.info("delete file, %s", str(pth))
            else:
                response = self._s.delete(pth, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("delete failed, %s", str(err))
            return 1

        _logger.debug("response %s", json.dumps(j, indent=4))

        return 0


    def list_datasets(self, dryrun : bool) -> int:
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
        headers = {"Authorization": f"Bearer {self.token_data}" }

        # print(headers)

        pth = f'{self.url}/dataset'

        j= {}

        try:
            if dryrun:
                _logger.info("List datasets")
            else:
                response = self._s.get(pth, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("list datasets failed, %s", str(err))
            return 1

        datasets = j.get("Datasets", [])

        fmt = "{:>9} | {:>40} | {:>30} | {:>10} | {:>10}"
        print(fmt.format("DatasetID", "DatasetName", "CreateDate", "Category", "Organization"))
        print("----------+------------------------------------------+--------------------------------+------------+---------------")
        for entry in datasets:
            print(fmt.format(entry["DatasetID"], entry["DatasetName"], entry["CreateDate"],  entry["Category"], entry["Organization"]))


        return 0


    def list_files(self, datasetid : int,  dryrun : bool) -> int:
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
        headers = {"Authorization": f"Bearer {self.token_data}" }

        files = []

        pth = f'{self.url}/dataset/{datasetid}/files?limit=0&extrafiles=true'

        j = {}

        try:
            if dryrun:
                _logger.info("List files in dataset %d", datasetid)
            else:
                response = self._s.get(pth, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                j = response.json()
        except requests.exceptions.HTTPError as err:
            _logger.error("list files failed, %s", str(err))
            return 1

        _logger.debug(json.dumps(j, indent=3))

        _files = j.get("data", [])
        files.extend(_files)

        """
        ...
         {
         "FileID": 59,
         "MFileName": "testupload1731423091_float_2009-10-10T00:10:18.000_2009-10-10T00:10:19.000_9_raw.zstd",
         "DatasetID": 3,
         "OriginName": "Ericsson",
         "StartDate": "2009-10-10T00:10:18.000Z",
         "StopDate": "2009-10-10T00:10:19.000Z",
         "FileSize": 2097152,
         "MetricEntries": 9,
         "MetricType": "float",
         "Uuid": "c666a272-b2d6-428a-bc3a-9a7675c40914",
         "ExtraFile": 0
         },
        {
            "FileID": 3,
            "MFileName": "apa.csv",
            "DatasetID": 1,
            "OriginName": "Ericsson",
            "StartDate": null,
            "StopDate": null,
            "FileSize": 1442,
            "MetricEntries": null,
            "MetricType": null,
            "Uuid": "0209882d-6f3b-4275-b92e-ff42baea7e36",
            "ExtraFile": 1
            },
        ...
        """

        num_files = 0
        total_size = 0
        fmt = "{:>6} | {:>30} | {:>30} | {:>10} | {:>12} | {}"
        print(fmt.format("FileID", "StartDate", "StopDate", "Entries", "FileSize", "MFileName"))
        print("-------+--------------------------------+--------------------------------+------------+--------------+-----------------------")
        for entry in files:
            # isExtra = entry.get('ExtraFile', 0) == 1

            print(fmt.format(entry["FileID"] or "n/a", entry["StartDate"] or "n/a", entry["StopDate"] or "n/a",  entry["MetricEntries"] or "n/a", entry["FileSize"] or "n/a", entry["MFileName"]))

            num_files += 1
            total_size += entry["FileSize"]

        if num_files > 0:
            print("-------+--------------------------------+--------------------------------+------------+--------------+-----------------------")
            print(fmt.format(num_files, "", "",  "", total_size, ""))


        return 0
