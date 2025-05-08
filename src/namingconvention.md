# Naming conventions

## Metric files

```
<name>_<type>_<time-start>_<time-end>_<entry-count>_<data-flag>.<extension>[.<compression-method>]
```

example: `history_float_2022-12-26T00:00:00_2022-12-27T00:00:00_140190_preprocessed_and_anonymized.pkl.zst`

| parameter | description |
|---|---|
| **name:** | Alfa numeric, usually originates in the data-source. <br/> Must be a well-formed string without underscores '_'. |
| **type:** | The type of the values in the entries. <br/> Should be one of ['uint', 'float', 'str', 'text', 'log'] |
| **time-start:** | Date and time of the first entry in the file. <br/> The date and time is separated by 'T'. <br/> Format: YYYY-MM-DDThh:mm:ss[.uuu]  |
| **time-end:** | Date and time of the last entry in the file. <br/> Format as specified in time-start. |
| **entry-count:** | A count of the entries in the data-set. |
| **data-flag:** | Indicates if this file has been filtered/anonymized or not. <br/> Possible values are either "raw" or some short descriptive statement.  |
| **extension:** | Indicates the format of the data file. <br/> Should be one of ['csv', 'pkl', 'parquet'] |
| **compression-method** | Indicates the compression method used, if any. <br/> Supported compressions: bz2, gz, zstd. <br/> Preferred compression: zstd.



## Log files

```
<name>_<time-start>_<time-end>_<entry-count>_<uncompressed-size>_<data-flag>[.<data-type>].<compression-method>
```

example: `logstash-flow_2023-02-16T23:59:56_2023-02-16T20:50:30_7721801_8.168GB_raw.json.zstd`

| parameter | description |
|---|---|
| **name:** | Alfa numeric, usually originates in the data-source. <br/> Must be a well-formed string without underscores '_'. |
| **time-start:** | Date and time of the first entry in the file. <br/> The date and time is separated by 'T'. <br/> Format: YYYY-MM-DDThh:mm:ss[.uuu]  |
| **time-end:** | Date and time of the last entry in the file. <br/> Format as specified in time-start. |
| **entry-count:** | A count of the number or entries or lines in the data-set. |
| **uncompressed-size:** | The size of the uncompressed data in human-readable. <br> Example: `<size><si-unit>` = 8.123GB. |
| **data-flag:** | Indicates if this file has been filtered/anonymized or not. <br/> Possible values are either "raw" or some short descriptive statement.  |
| **data-type:** | Indicates what kind of data the file contains. <br/> Example: json  |
| **compression-method:** | Indicates the compression method used. <br/> Supported compressions: bz2, gz, zstd. <br/> Preferred compression: zstd.  |
