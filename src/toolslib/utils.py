import re
import glob
import json
import logging
from datetime import datetime, timezone

# Set default level
logging.basicConfig(level=logging.WARN)
_logger = logging.getLogger('toolslib.utils')
_logger.setLevel(logging.INFO)
logging.VERBOSE = 5
logging.addLevelName(logging.VERBOSE, "VERBOSE")


def parse_info(filename : str):
    """
    Extracts information fields from named file needed when creating a new dataset

    Parameters
    ----------
    filename : str
        Name of information (Markdown) file

    Returns
    -------
    dict
        Containing key/values entry/data

    Raises
    ------
    """
    with open(filename, mode='r') as f:
        info = f.read()

    data = {}
    section = None
    txt = ''
    for line in info.split("\n"):

        m = re.fullmatch(r'#\s*(.*)', line)
        if m is not None:
            if (section is not None) and (txt != ''):
                data[section] = txt.strip()

            section = m.group(1).lower()

            if 'access' in section:
                section = 'access'
            elif 'category' in section:
                section = 'category'
            else:
                pass

            txt = ''
            continue

        if (line == '') and (txt == ''):
            continue

        if txt == '':
            txt = line
        else:
            txt = f"{txt}\n{line}"


    if (section not in data) and (txt != ''):
        data[section] = txt.strip()

    _tags = []
    tags = data.get("tags", "")
    for line in tags.split("\n"):

        _line = None

        _s = re.split(r"[*+-.0-9]+\s+", line)
        if (len(_s) > 1) and (_s[0] == ''):
            _line = _s[1]

        _line = _line or line

        _s = re.split(r",\s+", _line)
        if (len(_s) > 0) and (_s[0] != ''):
            _tags.extend(_s)


    data["tags"] = _tags
    return data


def validate_info(data : dict):
    """
    Inspects if all relevant fields are provided

    Parameters
    ----------
    data : dict
        Dictionary describing the new dataset

    Returns
    -------
    Boolean
        True if all keys are provided, else False

    Raises
    ------
    """
    for k in ["dataset", "category", "tenant", "short info", "long info", "tags"]:
        if k not in data:
            return False

    if data["category"].lower() not in ["metric", "log", "logs"]:
        return False

    return True


def get_all_src_files(src_list : list[str]):
    """
    Uses file globbing to find all files that can be uploaded

    Parameters
    ----------
    src_list : list[str]
        Filename pattern matching

    Returns
    -------
    list
        List of files fulfilling the pattern matching

    Raises
    ------
    """
    ret = []

    if not isinstance(src_list, list):
        return ret

    for s in src_list:
        if isinstance(s, str):
            _ret = glob.glob(s, recursive=False)
            ret.extend(_ret)

    return ret


def valid_date(s : str):
    """
    Inspects if provided date string in filename is on correct format


    Parameters
    ----------
    s : str
        Datestring

    Returns
    -------
    Boolean
        True, if date is valid, False if not

    Raises
    ------
    """
    date_pattern = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z?"
    m = re.search(date_pattern, s)

    return m is not None



def parse_filename(fname : str) -> tuple[str, dict]:
    """
    Inspects that filename follows the naming convention

    metric:
    <name>_<type>_<time-start>_<time-end>_<entry-count>_<data-flag>.<extension>[.<compression-method>]
    example: history_float_2022-12-26T00:00:00_2022-12-27T00:00:00_140190_preprocessed-and-anonymized.pkl.zst

    log:
    <name>_<time-start>_<time-end>_<entry-count>_<uncompressed-size>_<data-flag>[.<data-type>].<compression-method>
    example: logstash-flow_2023-02-16T23:59:56_2023-02-16T20:50:30_7721801_8.168GB_raw.json.zstd


    Parameters
    ----------
    fname : str
        File name

    Returns
    -------
    str, dict
        String is either "metric" or "log" depending on the filename
        Dict is parsed filename
            {"name": str,
             "type": str,
             "start": str,
             "stop": str,
             "count": str,
             "flag": str,
             "ext": str,
             "compression": str,
             "prefix": str
            }

    "extra", {}
         Default. Fits files that fails the naming convention and therefore is assumed to be extra file.

    Raises
    ------
    """
    regex_pattern = r"([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^_]+)"
    m = re.search(regex_pattern, fname)
    if m is not None:
        if valid_date(m.group(3)) and valid_date(m.group(4)):
            tail = m.group(6)
            tail_pattern = r"([^.]+)\.([^.]+)\.([^.]+)"
            t = re.search(tail_pattern, tail)
            if t is not None:
                return "metric", {"name": m.group(1),
                                  "type": m.group(2),
                                  "start": m.group(3),
                                  "stop": m.group(4),
                                  "count": m.group(5),
                                  "flag": t.group(1),
                                  "ext": t.group(2),
                                  "compression": t.group(3),
                                  "prefix": m.group(3)[0:4]
                                  }

            tail_pattern = r"([^.]+)\.([^.]+)"
            t = re.search(tail_pattern, tail)
            if t is not None:
                return "metric", {"name": m.group(1),
                                  "type": m.group(2),
                                  "start": m.group(3),
                                  "stop": m.group(4),
                                  "count": m.group(5),
                                  "flag": t.group(1),
                                  "ext": t.group(2),
                                  "prefix": m.group(3)[0:4]
                                  }
        else:
            # invalid date(s)
            pass



    # try log
    regex_pattern = r"([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^_]+)_([^.]+)\.(.*)"
    m = re.search(regex_pattern, fname)
    if m is not None:
        if valid_date(m.group(2)) and valid_date(m.group(3)):
            tail = m.group(7)
            tail_pattern = r"([^.]+)\.([^.]+)"
            t = re.search(tail_pattern, tail)
            if t is not None:
                return "log", {"name": m.group(1),
                               "start": m.group(2),
                               "stop": m.group(3),
                               "count": m.group(4),
                               "size": m.group(5),
                               "flag": m.group(6),
                               "type": t.group(1),
                               "compression": t.group(2),
                               "prefix": m.group(3)[0:4]
                               }


            return "log", {"name": m.group(1),
                           "start": m.group(2),
                           "stop": m.group(3),
                           "count": m.group(4),
                           "size": m.group(5),
                           "flag": m.group(6),
                           "compression": m.group(7),
                           "prefix": m.group(3)[0:4]
                           }
        else:
            # invalid date(s)
            pass

    return "extra", {}


def _parse_time(s: str) -> tuple[object, str]:
    """
    """
    if s == "":
        return ""

    try:
        time_f = float(s)
    except Exception as e:
        _logger.debug("Not epoch, it seems, %s", str(e))
        time_f = -1.0

    time_o = None
    if time_f > 1e9:
        time_s = time_f / 1e10

        if time_s > 1.0:
            # invalid format
            return None, ""

        try:
            time_o = datetime.fromtimestamp(time_f, timezone.utc)
        except Exception as e:
            _logger.debug("Not epoch, it seems, {}".format(e))
            return None, ""
    else:
        # last chance for parsing the date string
        try:
            time_o = datetime.fromisoformat(s)
        except Exception as e:
            _logger.debug("Invalid date format '{}', {}".format(s, e))
            return None, ""

    if time_o is None:
        # this shall NOT happen
        return None, ""

    time_ts = time_o.strftime("%Y-%m-%dT%H:%M:%S.%f")
    time_ts = re.sub(r'\.000000', '', time_ts)
    if '.' in time_ts:
        time_ts = time_ts[:-3]
    time_ts = f'{time_ts}Z'

    _logger.debug("time_ts {}".format(time_ts))

    return time_o, time_ts


# def shall_construct_name(data : dict | None) -> bool:
#     """
#     """
#     if data is None:
#         return False

#     prefix = data.get("prefix", "")
#     if prefix:
#         # all other fields must be unset
#         # must not be confusing naming
#         if data.get("datatype", "") != "":
#             raise Exception("Confusing: datatype is set")

#         if data.get("dataflag", "") != "":
#             raise Exception("Confusing: dataflag is set")

#         if data.get("start", "") != "":
#             raise Exception("Confusing: start is set")

#         if data.get("stop", "") != "":
#             raise Exception("Confusing: stop is set")

#         if data.get("count", 0) != 1:
#             raise Exception("Confusing: count is set")

#         if data.get("size", "") != "":
#             raise Exception("Confusing: size is set")

#         return False

#     # prefix is not set
#     if data.get("datatype", "") == "":
#         return False

#     if data.get("dataflag", "") == "":
#         return False

#     if data.get("start", "") == "":
#         return False

#     if data.get("stop", "") == "":
#         return False

#     if data.get("count", 0) <= 0:
#         return False

#     # if data.get("size", "") == "":
#     #     return False

#     return True


def create_filename(data : dict, fname : str, kind : str) -> tuple[bool, str]:
    """
    Creates a filename that follows the naming convention using data

    Parameters
    ----------
    data : dict
        Dict contains field data
           data = {
                    "datatype": str,
                    "dataflag": str,
                    "start": str,
                    "stop": str,
                    "count": int,
                    "size": str,
                }
    fname : str
        File name
    kind : str
        Kind of filename, "metric", or "log"

    Returns
    -------
    tuple[bool, str]
        Constructed filename, or "" fname if name cannot be determined

    Raises
    ------
    """
    if kind not in ["metric", "log"]:
        _logger.error("create_filename, unable to create a filename since 'kind' is not set, kind '%s'", kind)
        return False, ""

    # required fields are start, stop and count
    _logger.debug("create_filename, data %s", json.dumps(data))

    count = data.get("count", 0)
    if count <= 0:
        return False, ""

    start_o, start = _parse_time(data.get("start", ""))
    if start_o is None:
        return False, ""

    stop_o, stop = _parse_time(data.get("stop", ""))
    if stop_o is None:
        return False, ""

    # Sanity check
    if stop_o < start_o:
        _logger.error("Stop time is earlier tan start time")
        return False, ""

    # log
    # <name>_<time-start>_<time-end>_<entry-count>_<uncompressed-size>_<data-flag>[.<data-type>].<compression-method

    # metric
    # <name>_<type>_<time-start>_<time-end>_<entry-count>_<data-flag>.<extension>[.<compression-method>]

    # dataflag is also needed
    dataflag = data.get("dataflag", "")
    if dataflag == "":
        return False, ""

    # inspect the tails
    # fname = <base>.<extension>.<compression> ?
    base, extension, compression = "", "", ""

    tail_pattern = r"([^.]+)\.([^.]+)\.([^.]+)"
    m = re.search(tail_pattern, fname)
    if m is not None:
        base = m.group(1)
        extension = m.group(2)
        compression = m.group(3)
    else:
        # fname = <base>.<extension> ?

        tail_pattern = r"([^.]+)\.([^.]+)"
        m = re.search(tail_pattern, fname)
        if m is not None:
            base = m.group(1)
            extension = m.group(2)

    if (base == "") or (extension == ""):
        return False, ""

    def _pretty(abc):
        abc = re.sub('[^a-zA-Z0-9-]', '-', abc)
        ret = re.sub('[-]+', '-', abc)
        return ret

    base = _pretty(base)
    extension = _pretty(extension)
    dataflag = _pretty(dataflag)

    # Uncompressed size is mandatory for logs
    size = data.get("size", "")             # needed in log name
    datatype = data.get("datatype", "")     # needed in metric name

    if kind == "log":
        if size == "":
            _logger.error("Log file missing size parameter")
            return False, ""

        if compression == "":
            _logger.error("Log file is not compressed")
            return False, ""

        # log
        # <name>_<time-start>_<time-end>_<entry-count>_<uncompressed-size>_<data-flag>[.<data-type>].<compression-method

        if datatype:
            new_name = "{}_{}_{}_{}_{}_{}.{}.{}".format(base, start, stop, count, size, dataflag, extension, compression)
        else:
            new_name = "{}_{}_{}_{}_{}_{}.{}".format(base, start, stop, count, size, dataflag, compression)

    if kind == "metric":
        if datatype == "":
            _logger.error("Metric file is missing datatype")
            return False, ""

        # metric
        # <name>_<type>_<time-start>_<time-end>_<entry-count>_<data-flag>.<extension>[.<compression-method>]

        datatype = _pretty(datatype)

        new_name = "{}_{}_{}_{}_{}_{}.{}".format(base, datatype, start, stop, count, dataflag, extension)
        if compression != "":
            new_name = f'{new_name}.{compression}'

    return True, new_name


if __name__ == "__main__":
    s, _ = parse_filename("history_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_76Mb.json.zip")
    assert(s == "extra")

    s, d = parse_filename("history_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_76Mb_raw.json.bz2")
    assert(s == "log")
    assert(d["compression"] == "bz2")
    assert(d["type"] == "json")
    assert(d["flag"] == "raw")

    s, d = parse_filename("history_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_76Mb_raw.bz2")
    assert(s == "log")
    assert(d["compression"] == "bz2")
    assert(d["flag"] == "raw")

    s, d = parse_filename("history_float_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv.zip")
    assert(s == "metric")
    assert(d["compression"] == "zip")
    assert(d["ext"] == "csv")

    s, d = parse_filename("history_float_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv")
    assert(s == "metric")
    assert(d["ext"] == "csv")

    # ok
    data = {
            "datatype": "float",
            "dataflag": "raw",
            "start": "2022-12-26T00:00:00",
            "stop": "2022-12-26T01:00:00",
            "count": 700,
            "size": "8.1G",
        }
    ok, new_name = create_filename(data, "kenny.csv", "log")
    assert(not ok)  # no compression!
    print(new_name)

    ok, new_name = create_filename(data, "kenny.pkl.zst", "log")
    assert(ok)
    print(new_name)

    data = {
            "datatype": "float",
            "dataflag": "raw and juicy",
            "start": "1737645608",
            "stop": "1737645608.6",
            "count": 700,
            "size": "",
        }
    ok, new_name = create_filename(data, "kenny.csv", "metric")
    assert(ok)
    print(new_name)

    ok, new_name = create_filename(data, "kenny.pkl.zst", "metric")
    assert(ok)
    print(new_name)

    data = {
            "datatype": "float",
            "dataflag": "raw",
            "start": "1737645608",
            "stop": "1737645608.6",
            "count": 700,
            "size": "12343243",
        }
    ok, new_name = create_filename(data, "kenny.pkl.zst", "log")
    assert(ok)
    print(new_name)

    # error
    data = {
            "dataflag": "raw",
            "start": "1737645608",
            "stop": "1737645608.6",
            "count": 700,
        }
    ok, new_name = create_filename(data, "kenny", "metric")
    assert(not ok)
    print(new_name)


    data = {
            "datatype": "float",
            "dataflag": "raw",
            "start": "1737645608",
            "stop": "1737645608.6",
            "count": 700,
            "size": "12343243",
        }
    ok, new_name = create_filename(data, "ke nny.csv.zst", "log")
    assert(ok)
    print(new_name)

    data = {
            "datatype": "float",
            "dataflag": "raw",
            "start": "1737645608",
            "stop": "17370608.6",
            "count": 700,
            "size": "12343243",
        }
    ok, new_name = create_filename(data, "ke nny.csv.zst", "log")
    assert(not ok)
    print(new_name)

    data = {
            "datatype": "float",
            "dataflag": "raw",
            "start": "1737645608",
            "stop": "1737645607",
            "count": 700,
            "size": "12343243",
        }
    ok, new_name = create_filename(data, "kenny.csv.zst", "log")
    assert(not ok)
    print(new_name)
