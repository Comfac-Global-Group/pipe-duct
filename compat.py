# -*- coding: utf-8 -*-
"""
PySide compatibility shim for Comfac MEP Workbench.
Supports FreeCAD 0.21+ (Qt5/PySide2) and FreeCAD 1.0+ (Qt6/PySide6).
Falls back to legacy PySide (Qt4) for backwards compatibility.

Usage:
    from compat import QtWidgets, QtCore, QtGui
"""
try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore, QtGui
    except ImportError:
        from PySide import QtGui as QtWidgets
        from PySide import QtCore
        from PySide import QtGui
