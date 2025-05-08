# Example of dataset description text

```markdown
# Dataset
Dummy dataset

# Tenant
Ericsson

# Category: metric/log
metric

# Short Info
Short and catchy slogan

# Long Info
Longer and informative text about the dataset.
- Interesting fact 1.
- Interesting fact 3.

# Tags
tag1, tag2

# Access: open/closed
closed
```

# Usage
## Prerequisites
- User must exist in the Portal. In the examples below denoted ```user123```
- A token is created and downloaded. In the examples below denoted ```user.token```

### Naming convention
[See here.](./namingconvention.md)

## Create a dataset
```sh
./main.py -c info.md -U user123 -t user.token
```

## List datasets
```sh
./main.py -L -t user.token
```

## Upload file
### Upload a file that follow the data file naming convention
```sh
./main.py -U 17 -s "./dataset/file*.tgz" -t user.token
```

### Upload a file that does not follow the datafile naming convention.
Place file in ```README.md``` in the cloud storage as file ```/metadata/README.md```.
```sh
./main.py -U 17 -s ./dataset/README.md -t user.token -p metadata
```

## List files in dataset
```sh
./main.py -l 17 -t user.token
```

## Delete dataset
```sh
./main.py -d 17 -t user.token
```

## Setting another API server URL
```sh
$ ./main.py -a http://localhost:3001/v1 ...

$ PORTAL_URL=http://localhost:3001/v1 ./main.py ...
```

# Example
In the examples below, we use live portal where we access the API on ```https://portal.wara-ops.org/api/v1``` which is default.
Other API servers, e.g., development servers, can be set wuth either command line argumant or setting environment variab,le.

```sh
# List available datasets
$ ./main.py -L -t /tmp/user01_token
DatasetID |                              DatasetName |                     CreateDate |   Category | Organization
----------+------------------------------------------+--------------------------------+------------+---------------
        1 |                              ERDCmetrics |       2023-12-13T09:21:35.000Z |     metric |   Ericsson
        2 |                                 ERDClogs |       2023-12-13T10:30:03.000Z |        log |   Ericsson
        3 |                                   5Gdata |       2023-12-13T10:41:59.000Z |     metric |   Ericsson
        4 |                                      srs |       2023-12-13T11:03:49.000Z |     metric |   Ericsson
        5 |                            ControlSystem |       2024-01-08T12:13:35.000Z |     metric |        ESS
        6 |                                CrashDump |       2024-01-08T12:21:20.000Z |        log | Schneider-Electric
        7 |                          ERDClogs-parsed |       2024-02-16T06:51:10.000Z |        log |   Ericsson
       14 |                          SRS-Positioning |       2024-09-23T06:38:23.000Z |     metric |   Ericsson
       15 |             ISAC-midband-drone-detection |       2024-10-11T12:40:53.000Z |     metric |   Ericsson
       16 |                      AdvenicaLogAnalysis |       2024-11-27T08:27:51.000Z |        log |   Advenica
       17 |                       Kockums-Kubernetes |       2024-12-12T12:37:03.000Z |        log | SAAB-Kockums



# List files in dataset
$ /main.py -l 1 -t
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     1 |       2022-11-16T00:00:00.000Z |       2022-11-17T00:00:00.000Z |     637438 |      5521085 | history_2022-11-16T00:00:00_2022-11-17T00:00:00_637438.pkl.bz2
     4 |       2022-11-17T00:00:00.000Z |       2022-11-18T00:00:00.000Z |     630806 |      5458175 | history_2022-11-17T00:00:00_2022-11-18T00:00:00_630806.pkl.bz2
...
 99004 |       2024-01-31T21:00:00.000Z |       2024-01-31T21:59:59.000Z |     869106 |      5964930 | history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_869106.pkl.bz2
 99005 |       2024-01-31T22:00:00.000Z |       2024-01-31T22:59:59.000Z |     868935 |      5956555 | history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_868935.pkl.bz2
 99006 |       2024-01-31T23:00:00.000Z |       2024-01-31T23:59:59.000Z |     868797 |      5956084 | history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_868797.pkl.bz2
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
 15744 |                                |                                |            | 148268459480 |


# Create a dataset
$ ./main.py -a http://127.0.0.1:3001/v1 -c dummy.md -u user01 -t /tmp/user01_token
DatasetID | ContainerName
----------+--------------------------------------------------------------------------------------------------
     20 | waraops_qtorgho_ade10eab-63a3-4946-8d5d-a298ddf0ad66_Ericsson_Example-dataset

# List files (Should not be any!)
$ ./main.py -l 20 -u user01 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------


# Upload an extrafile. Note: prefix (destination catalog) must be provided for extrafiles
$ ./main.py -U 20 -s README.md -t /tmp/user01_token -p testing
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
README.md                                          | testing/README.md

# Upload datafiles.
# Note 1: it can be a good idea to make a dry run first
# Note 2: Globbing requires double quotes
$ ls -l hist*
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:24 history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv

$ ./main.py -U 20 -s "history_uint_2024-01-31T2*" -t /tmp/user01_token --dryrun
INFO:toolslib.upload:_upload_data {
    "datatype": "uint",
    "dataflag": "raw",
    "start": "2024-01-31T23:00:00Z",
    "stop": "2024-01-31T23:59:59Z",
    "count": 3000
}
INFO:toolslib.upload:_upload_data {
    "datatype": "uint",
    "dataflag": "raw",
    "start": "2024-01-31T22:00:00Z",
    "stop": "2024-01-31T22:59:59Z",
    "count": 2000
}
INFO:toolslib.upload:_upload_data {
    "datatype": "uint",
    "dataflag": "raw",
    "start": "2024-01-31T21:00:00Z",
    "stop": "2024-01-31T21:59:59Z",
    "count": 1000
}
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------

$ ./main.py -U 20 -s "history_uint_2024-01-31T2*" -t /tmp/user01_token
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv | 2024/history_uint_2024-01-31T23:00:00.000_2024-01-31T23:59:59.000_3000_raw.csv
history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv | 2024/history_uint_2024-01-31T22:00:00.000_2024-01-31T22:59:59.000_2000_raw.csv
history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv | 2024/history_uint_2024-01-31T21:00:00.000_2024-01-31T21:59:59.000_1000_raw.csv

# Delete dataset
$ ./main.py -d 20 -t /tmp/user01_token
```

# More examples
In the examples below, we use a dev portal where we access the API on ```http://127.0.0.1:3001/v1```.

## Create a dataset
Yes, same as above.
```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -L -t /tmp/user01_token
DatasetID |                              DatasetName |                     CreateDate |   Category | Organization
----------+------------------------------------------+--------------------------------+------------+---------------

$ ./main.py -a http://127.0.0.1:3001/v1 -c dummy.md -u user01 -t /tmp/user01_token
DatasetID | ContainerName
----------+--------------------------------------------------------------------------------------------------
        7 | waraops_qtorgho_bb2019ca-0ec3-4b63-b0a8-9b931e52daeb_Ericsson_Dummy-dataset
```

## Uplod an extra file.
When the ```prefix``` argument, ```-p```, is set, the provided file will be uploaded as an extra file regardless of other parameters.

```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -U 7 -s extrafile.csv.zst -p larry -t /tmp/user01_token
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
extrafile.csv.zst                                  | larry/extrafile.csv.zst
```

Upload a file and rename it.
```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -U 7 -s extrafile.csv.zst -p subdir/newname.csv.zst -t /tmp/user01_token
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
extrafile.csv.zst                                  | subdir/newname.csv.zst
```

## List all files so far.
```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -l 7 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
    72 |                            n/a |                            n/a |        n/a |         1442 | extrafile.csv.zst
    73 |                            n/a |                            n/a |        n/a |         1442 | newname.csv.zst
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     2 |                                |                                |            |         2884 |
```

## Upload data files
Globbing is allowed. Notice here that all files follow the naming convention.
```sh
$ ls -l metric
total 24
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:23 history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv
-rw-r--r--  1 qtorgho  staff  1442 Jan 20 13:24 history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv

$ ./main.py -a http://127.0.0.1:3001/v1 -U 7 -t /tmp/user01_token -s "metric/history*"
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
metric/history_uint_2024-01-31T23:00:00Z_2024-01-31T23:59:59Z_3000_raw.csv | 2024/history_uint_2024-01-31T23:00:00.000_2024-01-31T23:59:59.000_3000_raw.csv
metric/history_uint_2024-01-31T22:00:00Z_2024-01-31T22:59:59Z_2000_raw.csv | 2024/history_uint_2024-01-31T22:00:00.000_2024-01-31T22:59:59.000_2000_raw.csv
metric/history_uint_2024-01-31T21:00:00Z_2024-01-31T21:59:59Z_1000_raw.csv | 2024/history_uint_2024-01-31T21:00:00.000_2024-01-31T21:59:59.000_1000_raw.csv
```
Alternatively, the argument ```-s``` can be repeated, e.g.,
```sh
... -s file1 -s file2 -s file3 ...
```
List uploaded files so far
```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -l 7 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
    72 |                            n/a |                            n/a |        n/a |         1442 | extrafile.csv.zst
    73 |                            n/a |                            n/a |        n/a |         1442 | newname.csv.zst
    74 |       2024-01-31T23:00:00.000Z |       2024-01-31T23:59:59.000Z |       3000 |         1442 | history_uint_2024-01-31T23:00:00.000_2024-01-31T23:59:59.000_3000_raw.csv
    75 |       2024-01-31T22:00:00.000Z |       2024-01-31T22:59:59.000Z |       2000 |         1442 | history_uint_2024-01-31T22:00:00.000_2024-01-31T22:59:59.000_2000_raw.csv
    76 |       2024-01-31T21:00:00.000Z |       2024-01-31T21:59:59.000Z |       1000 |         1442 | history_uint_2024-01-31T21:00:00.000_2024-01-31T21:59:59.000_1000_raw.csv
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     5 |                                |                                |            |         7210 |

```

## Upload a file using arguments to describe the data content
In this example, we have information (arguments) to construct both a ```metric``` file and a ```log``` file which the tool complains about.
```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -U 7 -s extrafile3.csv -t /tmp/user01_token \
--start "$(date +%s)" \
--stop "$(date +%s)" \
--count 1000 \
--flag raw \
--dtype float
ERROR:toolslib.utils:create_filename, unable to create a filename since 'kind' is not set, kind ''
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
```
We need to hint that the file is a ```metric``` file.
```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -U 7 -s extrafile3.csv -t /tmp/user01_token \
--start "$(date +%s)" \
--stop "$(date +%s)" \
--count 1000 \
--flag raw \
--dtype float \
--kind metric
Source                                             | Dest
---------------------------------------------------+-------------------------------------------------------------
extrafile3.csv                                     | 2025/extrafile3_float_2025-01-25T10:19:05.000_2025-01-25T10:19:05.000_1000_raw.csv
```
Note: using parameters to describe a data file only applies when a single file shall be uploaded. Also, ```start``` and ```stop``` can be epoch, i.e., time in seconds since 1970-01-01.

List the uploaded files so far.
```sh
$ ./main.py -a http://127.0.0.1:3001/v1 -l 7 -t /tmp/user01_token
FileID |                      StartDate |                       StopDate |    Entries |     FileSize | MFileName
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
    72 |                            n/a |                            n/a |        n/a |         1442 | extrafile.csv.zst
    73 |                            n/a |                            n/a |        n/a |         1442 | newname.csv.zst
    74 |       2024-01-31T23:00:00.000Z |       2024-01-31T23:59:59.000Z |       3000 |         1442 | history_uint_2024-01-31T23:00:00.000_2024-01-31T23:59:59.000_3000_raw.csv
    75 |       2024-01-31T22:00:00.000Z |       2024-01-31T22:59:59.000Z |       2000 |         1442 | history_uint_2024-01-31T22:00:00.000_2024-01-31T22:59:59.000_2000_raw.csv
    76 |       2024-01-31T21:00:00.000Z |       2024-01-31T21:59:59.000Z |       1000 |         1442 | history_uint_2024-01-31T21:00:00.000_2024-01-31T21:59:59.000_1000_raw.csv
    77 |       2025-01-25T10:19:05.000Z |       2025-01-25T10:19:05.000Z |       1000 |         1442 | extrafile3_float_2025-01-25T10:19:05.000_2025-01-25T10:19:05.000_1000_raw.csv
-------+--------------------------------+--------------------------------+------------+--------------+-----------------------
     6 |                                |                                |            |         8652 |

```
