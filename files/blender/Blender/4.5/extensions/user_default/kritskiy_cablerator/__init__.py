'''
Copyright (C) 2020 SERGEY KRITSKIY
kritskiy.sergey@gmail.com
https://gumroad.com/kritskiy
Created by Sergey Kritskiy
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.
    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''
''' Hi stranger. You'll only find some terrible code here and I don't know how it works '''
bl_info = {
"name": "Cablerator",
"description": "Create cables by setting a start and an end points from two faces. And more.",
"category": "Object",
"author": "Sergey Kritskiy",
"version": (1, 4, 11),
"location": "Add > Create Cable or Cablerator Menu shortcut (Shift+Alt+C by default)",
'wiki_url': 'https://cablerator.readthedocs.io/en/latest/',
"blender": (2, 80, 0),}
modulesNames = ['lib', 'ui', 'inits', 'hooks', 'helpers',
'createCablePrefs', 'createCable', 'createCableFromEdge', 'createCableFromSelected',
'editCable', 'createConnector', 'createSegment', 'createGeoCables',
'drawCable', 'connectCables', 'splitCable', 'splitRecable',
'simulateCable', 'massiveCables', 'insulate', 'rope', 'assets',
'typing', 'helpers_node', 'node_serilizer']
import bpy
import sys
import importlib
modulesFullNames = {}
for currentModuleName in modulesNames:
    if 'DEBUG_MODE' in sys.argv:
        modulesFullNames[currentModuleName] = ('{}'.format(currentModuleName))
    else:
        modulesFullNames[currentModuleName] = ('{}.{}'.format(__name__, currentModuleName))
for currentModuleFullName in modulesFullNames.values():
    if currentModuleFullName in sys.modules:
        importlib.reload(sys.modules[currentModuleFullName])
    else:
        globals()[currentModuleFullName] = importlib.import_module(currentModuleFullName)
        setattr(globals()[currentModuleFullName], 'modulesNames', modulesFullNames)
def register():
    for currentModuleName in modulesFullNames.values():
        if currentModuleName in sys.modules:
            if hasattr(sys.modules[currentModuleName], 'register'):
                sys.modules[currentModuleName].register()
def unregister():
    for currentModuleName in modulesFullNames.values():
        if currentModuleName in sys.modules:
            if hasattr(sys.modules[currentModuleName], 'unregister'):
                sys.modules[currentModuleName].unregister()
if __name__ == "__main__":
    register()