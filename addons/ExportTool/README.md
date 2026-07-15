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

The 'filter' parameter is optional. It can be the name of a Person custom filter or one of the following keywords:

* descendants
* descendant_families
* ancestors
* common_ancestor

If one of these is used then also the parameter 'gramps_id' must be specified and the filter is applied to the corresponding person.

If the filter name contains spaces then it must be in quotes like in the example above.

If no filter is specified then the complete database is exported.

For .gpkg files the media is included. No other export options are supported. 




