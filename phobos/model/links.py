#!/usr/bin/python
# coding=utf-8

"""
.. module:: phobos.exporter
    :platform: Unix, Windows, Mac
    :synopsis: TODO: INSERT TEXT HERE

.. moduleauthor:: Kai von Szadowski

Copyright 2014, University of Bremen & DFKI GmbH Robotics Innovation Center

This file is part of Phobos, a Blender Add-On to edit robot models.

Phobos is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License
as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.

Phobos is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Phobos.  If not, see <http://www.gnu.org/licenses/>.

File links.py

Created on 14 Apr 2014
"""

import bpy
import mathutils
import math
import re
import phobos.defs as defs
import phobos.utils.naming as nUtils
import phobos.utils.blender as bUtils
import phobos.utils.selection as sUtils
import phobos.model.inertia as inertia
import phobos.model.geometries as geometrymodel
from phobos.phoboslog import log


def getGeometricElements(link):
    # DOCU add some docstring
    visuals = []
    collisions = []
    if 'visual' in link:
        visuals = [link['visual'][v] for v in link['visual']]
    if 'collision' in link:
        collisions = [link['collision'][v] for v in link['collision']]
    return collisions + visuals


def createLink(link):
    """Creates the blender representation of a given link and its parent joint.

    :param link: The link you want to create a representation of.
    :type link: dict
    :return: bpy_types.Object -- the newly created blender link object.
    """
    # create armature/bone
    bUtils.toggleLayer(defs.layerTypes['link'], True)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.armature_add(layers=bUtils.defLayers([defs.layerTypes['link']]))
    newlink = bpy.context.active_object
    # Move bone when adding at selected objects location
    if 'matrix' in link:
        newlink.matrix_world = link['matrix']
    newlink.phobostype = 'link'
    if link['name'] in bpy.data.objects.keys():
        log('Object with name of new link already exists: ' + link['name'], 'WARNING')
    newlink.name = link['name']
    newlink["link/name"] = link['name']

    # set the size of the link
    elements = getGeometricElements(link)
    if elements:
        scale = max((geometrymodel.getLargestDimension(e['geometry']) for e in elements))
    else:
        scale = 0.2

    # use scaling factor provided by user
    if 'scale' in link:
        scale *= link['scale']
    newlink.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(scale=True)

    # add custom properties
    for prop in link:
        if prop.startswith('$'):
            for tag in link[prop]:
                newlink['link/'+prop[1:]+'/'+tag] = link[prop][tag]

    # create inertial
    if 'inertial' in link:
        inertia.createInertial(link['name'], link['inertial'], newlink)

    # create visual elements
    if 'visual' in link:
        for v in link['visual']:
            visual = link['visual'][v]
            geometrymodel.createGeometry(visual, 'visual')

    # create collision elements
    if 'collision' in link:
        for c in link['collision']:
            collision = link['collision'][c]
            geometrymodel.createGeometry(collision, 'collision')

    return newlink


def deriveLinkfromObject(obj, scale=0.2, parent_link=True, parent_objects=False, nameformat=''):
    """Derives a link from an object using its name, transformation and parenting.

    :param obj: object to derive a link from
    :type obj: bpy_types.Object
    :param scale: scale factor for bone size
    :type scale: float
    :param parent_link: whether to automate the parenting of the new link or not.
    :type parent_link: bool
    :param parent_objects: whether to parent all the objects to the new link or not
    :type parent_objects: bool
    :param nameformat: re-formatting template for obj names
    :type nameformat: str
    :return: newly created link
    """
    log('Deriving link from ' + nUtils.getObjectName(obj), level="INFO")
    try:
        nameparts = [p for p in re.split('[^a-zA-Z]', nUtils.getObjectName(obj)) if p != '']
        linkname = nameformat.format(*nameparts)
    except IndexError:
        log('Invalid name format (indices) for naming: ' + nUtils.getObjectName(obj), 'WARNING')
        linkname = 'link_' + nUtils.getObjectName(obj)
    link = createLink({'scale': scale, 'name': linkname, 'matrix': obj.matrix_world})

    # parent link to object's parent
    if parent_link:
        if obj.parent:
            sUtils.selectObjects([link, obj.parent], True, 1)
            if obj.parent.phobostype == 'link':
                bpy.ops.object.parent_set(type='BONE_RELATIVE')
            else:
                bpy.ops.object.parent_set(type='OBJECT')
    # parent children of object to link
    if parent_objects:
        children = [obj] + sUtils.getImmediateChildren(obj)
        sUtils.selectObjects(children, True, 0)
        bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
        sUtils.selectObjects([link] + children, True, 0)
        bpy.ops.object.parent_set(type='BONE_RELATIVE')
    return link


def placeChildLinks(model, parent):
    """Creates parent-child-relationship for a given parent and all existing children in Blender.

    :param parent: This is the parent link you want to set the children for.
    :type: dict
    """
    bpy.context.scene.layers = bUtils.defLayers(defs.layerTypes['link'])
    children = []
    for l in model['links']:
        if 'parent' in model['links'][l] and model['links'][l]['parent'] == parent['name']:
            children.append(model['links'][l])
    for child in children:
        # 1: set parent relationship (this makes the parent inverse the inverse of the parents world transform)
        parentLink = bpy.data.objects[parent['name']]
        childLink = bpy.data.objects[child['name']]
        sUtils.selectObjects([childLink, parentLink], True, 1)
        bpy.ops.object.parent_set(type='BONE_RELATIVE')
        # 2: move to parents origin by setting the world matrix to the parents world matrix
        # removing this line does not seem to make a difference (TODO delete me?)
        childLink.matrix_world = parentLink.matrix_world

        # TODO delete me?
        # #bpy.context.scene.objects.active = childLink
        # if 'pivot' in child:
        #     pivot = child['pivot']
        #     cursor_location = bpy.context.scene.cursor_location
        #     bpy.context.scene.cursor_location = mathutils.Vector((-pivot[0]*0.3, -pivot[1]*0.3, -pivot[2]*0.3))
        #     bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        #     bpy.context.scene.cursor_location = cursor_location

        # 3: apply local transform as saved in model (changes matrix_local)
        location = mathutils.Matrix.Translation(child['pose']['translation'])
        rotation = mathutils.Euler(tuple(child['pose']['rotation_euler']), 'XYZ').to_matrix().to_4x4()
        transform_matrix = location * rotation
        childLink.matrix_local = transform_matrix
        # 4: be happy, as world and basis are now the same and local is the transform to be exported to urdf
        # 5: take care of the rest of the tree
        placeChildLinks(model, child)


def placeLinkSubelements(link):
    """Places visual and collision objects for a given link.

    :param link: The parent link you want to set the subelements for
    :type link: dict
    """
    elements = getGeometricElements(link)
    bpy.context.scene.layers = bUtils.defLayers([defs.layerTypes[t] for t in defs.layerTypes])
    parentlink = bpy.data.objects[link['name']]
    log('Placing subelements for link: ' + link['name'] + ': ' + ', '.join([elem['name'] for elem in elements]), 'DEBUG')
    for element in elements:
        if 'pose' in element:
            log('Pose detected for element: ' + element['name'], 'DEBUG')
            location = mathutils.Matrix.Translation(element['pose']['translation'])
            rotation = mathutils.Euler(tuple(element['pose']['rotation_euler']), 'XYZ').to_matrix().to_4x4()
        else:
            log('No pose in element: ' + element['name'], 'DEBUG')
            location = mathutils.Matrix.Identity(4)
            rotation = mathutils.Matrix.Identity(4)
        try:
            obj = bpy.data.objects[element['name']]
        except KeyError:
            log('Missing link element for placement: ' + element['name'], 'ERROR')
            continue
        sUtils.selectObjects([obj, parentlink], True, 1)
        bpy.ops.object.parent_set(type='BONE_RELATIVE')
        obj.matrix_local = location * rotation
        try:
            obj.scale = mathutils.Vector(element['geometry']['scale'])
        except KeyError:
            log('No scale defined for element ' + element['name'], 'DEBUG')
