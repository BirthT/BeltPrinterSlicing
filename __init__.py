# Copyright (c) 2021 BirthT,llc.
# This plugin is released under the terms of the LGPLv3 or higher.

from . import BeltPlugin

def getMetaData():
    return {}

def register(app):
    return {"extension": BeltPlugin.BeltPlugin()}
