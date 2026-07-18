ExportTool
----------

Author: kari.kujansuu@gmail.com<br>
2025-2026

Tool that can execute an 'export' operation from the command line (CLI) while applying a Person filter.

This is an experimental tool.

Syntax:

```
$ gramps -O <database> -a tool -p name=ExportTool,filename=<output>,filter=<filter name>,gramps_id=<id>
```

Sample run:

```
$ gramps -O example_gramps -a tool -p name=ExportTool,filename=test.gramps,filter="Probably alive"
Opened successfully!
Performing action: tool.
Using options string: name=ExportTool,filename=test.gramps,filter=Probably alive
Filter 'Probably alive' found
...
Cleaning up.
```

This supports only GEDCOM (.ged) and Gramps (.gramps or .gpkg) output files.

The output file 'filename' is overwritten if it already exists.

The optional 'filter' parameter is the name of a Person custom filter. If the filter name contains spaces then it must be in quotes like in the example above.

However, if the parameter 'gramps_id' is specified then the filter parameter should be one of the following keywords:

* descendants
* descendant_families
* ancestors
* common_ancestor

The parameter 'gramps_id' should refer to a person in the database. The filter selected by one of the keywords above is then applied to the person.

If no filter is specified then the complete database is exported.

For .gpkg files the media files are included. No other export options are supported. 




