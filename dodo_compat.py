# -*- coding: utf-8 -*-
"""
Dodo compatibility shim for star-import style.
Re-exports QtWidgets, QtCore, and QtGui classes as bare names
to preserve Dodo's `from PySide.QtGui import *` behavior.

Usage:
    from dodo_compat import *
"""
from compat import QtWidgets, QtCore, QtGui

# Re-export widget classes (moved to QtWidgets in Qt5/Qt6)
for _name in dir(QtWidgets):
    if not _name.startswith('_'):
        globals()[_name] = getattr(QtWidgets, _name)

# Re-export GUI classes (stayed in QtGui)
for _name in dir(QtGui):
    if not _name.startswith('_'):
        globals()[_name] = getattr(QtGui, _name)

# Re-export core classes (stayed in QtCore)
for _name in dir(QtCore):
    if not _name.startswith('_'):
        globals()[_name] = getattr(QtCore, _name)
