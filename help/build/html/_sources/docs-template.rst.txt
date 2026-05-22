Documentation Page Template
===========================

Use this file as a starting point for new Sphinx pages in ``help/source``.

How To Use This Template
------------------------

1. Copy this file to a new ``.rst`` filename in ``help/source``.
2. Replace the title and section text with your topic.
3. Add the new filename, without ``.rst``, to a toctree in ``index.rst``.
4. Run ``run_sphinx_documentation.bat`` from the plugin root.

Short Introduction
------------------

Write one short paragraph that explains what this page is for and when a user
or developer should read it.

Main Section
------------

Use normal paragraphs for explanation.

* Use bullet lists for short grouped items.
* Keep lists flat and direct.
* Prefer simple reStructuredText over advanced directives.

Steps
-----

1. First step.
2. Second step.
3. Third step.

Code Example
------------

.. code-block:: python

   print("example")

Note
----

.. note::

   Add notes sparingly. They are most useful for prerequisites, caveats, or
   workflow constraints that are easy to miss.

Image Example
-------------

.. figure:: ../../images/foldmap.png
   :alt: Example figure

   Replace this with a project image when the page needs a figure.