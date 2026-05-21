Status and Roadmap
==================

Project Status
--------------

Roll was first published on GitHub on 8 February 2024 and first released on
the QGIS plugin website on 13 March 2024.

As of version 0.3.3, Roll is no longer considered experimental. As of version
0.4.6, it is compatible with Qt 6 and therefore ready for QGIS 4.0. As of
version 0.7.0, the project includes substantial Numba-based optimization for
binning from templates and binning from geometry.

Current Characteristics
-----------------------

Roll uses memory-mapped analysis storage instead of a relational database for
full binning output. This matches the project workload better than row-based
storage with indexing and transaction overhead.

The plugin works best on one or two QHD displays or larger. Large trace tables
are handled in chunks to avoid overwhelming the Qt model/view system with very
large in-memory table allocations.

Project Size
------------

On 6 May 2026, the project contained:

* 27,482 production Python source lines across 109 files;
* 6,834 test Python source lines across 31 files; and
* 34,316 total Python source lines across 140 files.

For context:

* total Python lines including blanks and comments: 50,749;
* non-blank Python lines: 40,551; and
* the single ``.ui`` file adds 1,703 non-blank XML lines, although that is not
  included in the Python SLOC count.

Experimental Code Flag
----------------------

Roll currently exposes a ``use experimental code`` setting. This allows newer
binning and geometry-generation routines to be tested in realistic workflows
before they fully replace legacy implementations.

This split exists because survey behavior depends on many interacting factors,
including blocks, templates, seeds, seed types, and geometry patterns. A safer
incremental rollout is therefore more useful than a hard cut-over.

To Do
-----

Current roadmap items include:

* improve analysis capabilities, including ideas around multiple suppression
  and DMO smear; and
* expand the 3D layout view introduced in version 0.6.8.