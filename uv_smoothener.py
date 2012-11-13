# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    'name': "Aligning UV-coords",
    'author': "Mathias Weitz",
    'version': (1, 0, 0),
    'blender': (2, 6, 4),
    'api': 51206,
    'location': "IMAGE_EDITOR > UI",
    'description': "various tricks on UV",
    'category': 'UV'}
    
import bpy 
from bpy.props import *
import math 
import mathutils 
from math import pi 
from mathutils import Vector, Matrix

class thickface(object):
    __slots__= "v", "uv", "no", "area", "edge_keys"
    def __init__(self, face, uv_layer, mesh_verts):
        self.v = [mesh_verts[i] for i in face.vertices]
        self.uv = [uv_layer[i].uv for i in face.loop_indices]

        self.no = face.normal
        self.area = face.area
        self.edge_keys = face.edge_keys
        
class MessageOperator(bpy.types.Operator):
    bl_idname = "error.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()
 
    def execute(self, context):
        self.report({'INFO'}, self.message)
        print(self.message)
        return {'FINISHED'}
 
    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=200)
 
    def draw(self, context):
        self.layout.label("Notice")
        row = self.layout.row(align=True)
        row.alignment = 'EXPAND'
        row.prop(self, "message")
        #row = self.layout.split(0.80)
        #row.label("press ok and leave dialog") 
        #row.operator("error.ok")
        
class OkOperator(bpy.types.Operator):
    bl_idname = "error.ok"
    bl_label = "OK"
    def execute(self, context):
        return {'FINISHED'}

class UVTest(bpy.types.Operator):
    '''uv align'''
    bl_idname = 'uv.linealign'
    bl_label = 'linealign'
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return (obj and obj.type == 'MESH')

    def execute(self, context):
        #print ('***************')
        error = 0
        active = bpy.context.active_object
        bpy.ops.object.mode_set(mode='OBJECT')
        me = active.data
        
        if not me.uv_textures: 
            # Mesh has no UV Coords, don't bother.
            me.uv_textures.new()
            
        # getting the edges of a mesh-face aligned to the edge of a uv-face
        # the results are in edge with (vertindex_0, vertindex_1, uv_0, uv_1)
        # there could be more than one entry for vertindex_0, vertindex_1
        uv_layer = me.uv_layers.active.data
        markedUV = {}
        edges = []
        verts2uv = {}
        vert2vert = {}
        #me_vertices = me.vertices 
        #me_edges = me.edges
        #edges = [e for e in me_edges if me.vertices[e.vertices[0]].select and me.vertices[e.vertices[1]].select]
        for i,face in enumerate(me.polygons):
            for ii in range(len(face.loop_indices)):
                iip = (ii + 1) % len(face.loop_indices);
                iv0 = face.vertices[ii]
                iv1 = face.vertices[iip]
                uvi0 = ii
                uvi1 = iip
                if iv1 < iv0:
                    iv0 = face.vertices[iip]
                    iv1 = face.vertices[ii]
                    uvi0 = iip
                    uvi1 = ii
                    
                v0 = me.vertices[iv0]
                v1 = me.vertices[iv1]
                if v0.select:
                    markedUV[face.loop_indices[ii]] = iv0
                if v1.select:
                    markedUV[face.loop_indices[iip]] = iv1
                if v0.select and v1.select:
                    k = (iv0,iv1,face.loop_indices[uvi0],face.loop_indices[uvi1])
                    edges.append(k)
                    if iv0 not in vert2vert:
                        vert2vert[iv0] = []
                    if iv1 not in vert2vert:
                        vert2vert[iv1] = []
                    if iv0 not in vert2vert[iv1]:
                        vert2vert[iv1].append(iv0)
                    if iv1 not in vert2vert[iv0]:
                        vert2vert[iv0].append(iv1)
                    
                if face.loop_indices[uvi0] not in verts2uv:
                    verts2uv[face.loop_indices[uvi0]] = [iv0, uv_layer[face.loop_indices[uvi0]].uv.copy()]   
                if face.loop_indices[uvi1] not in verts2uv:
                    verts2uv[face.loop_indices[uvi1]] = [iv1, uv_layer[face.loop_indices[uvi1]].uv.copy()]
            
        #print (edges)
        #print ("len(verts2uv)", len(verts2uv))
        #print (vert2vert)
        
        # sorting the verts along the edges
        vertsOrder = []
        for vi, vin in vert2vert.items():
            if len(vin) == 1:
                vertsOrder.append(vi)
                vertsOrder.append(vin[0])
                break
        # TODO: if there is no start in the loop of the mesh
        # try to find a start in the verts of the UV-Mesh
        if 0 < len(vertsOrder):
            b = True
            maxc = 10000
            while b and 0 < maxc:
                b = False
                maxc -= 1
                v = vert2vert[vertsOrder[-1]]
                vn = v[0]
                if vn == vertsOrder[-2]:
                    if 1 < len(v):
                        vn = v[1]
                    else:
                        vn = None
                if vn != None:
                    vertsOrder.append(vn)
                    b = True
            
            # sorting the UV-Edges
            uvEdgeOrder = [[],[]]
            dist = 0.0
            if 1 < len(vertsOrder):
                for i in range(len(vertsOrder) - 1):
                    dist += (me.vertices[vertsOrder[i]].co - me.vertices[vertsOrder[i+1]].co).length
                    # the second uv-line can remain zero in the case of an open edge
                    if (len(uvEdgeOrder[0]) == i + 1 and (len(uvEdgeOrder[1]) == i + 1 or len(uvEdgeOrder[1]) == 0)) \
                        or i == 0:
                        vi0 = vertsOrder[i]
                        vi1 = vertsOrder[i+1]
                        for e in edges:
                            found = False
                            if e[0] == vi0 and e[1] == vi1:
                                #print ('->', e);
                                uv0, uv1 = e[2], e[3]
                                found = True
                            if e[0] == vi1 and e[1] == vi0:
                                #print ('-<', e);
                                uv0, uv1 = e[3], e[2]
                                found = True
                            if found:
                                if i == 0:
                                    if len(uvEdgeOrder[0]) == 0:
                                        uvEdgeOrder[0] = [uv0, uv1]
                                    else:
                                        uvEdgeOrder[1] = [uv0, uv1]
                                else:
                                    d0 = (uv_layer[uv0].uv - uv_layer[uvEdgeOrder[0][i]].uv).length
                                    d1 = 100.0
                                    if 0 < len(uvEdgeOrder[1]):
                                        d1 = (uv_layer[uv0].uv - uv_layer[uvEdgeOrder[1][i]].uv).length
                                    #print ("add",e, d0, d1, uvEdgeOrder)
                                    if abs(d0 - d1) < 1e-8:
                                        if len(uvEdgeOrder[1]) < len(uvEdgeOrder[0]):
                                            uvEdgeOrder[1].append(uv1)
                                        else:
                                            uvEdgeOrder[0].append(uv1)
                                    else:
                                        if d0 < d1:
                                            uvEdgeOrder[0].append(uv1)
                                        else:
                                            uvEdgeOrder[1].append(uv1)
                                
                            #print (i,uv0.uv, uv1.uv)
                    else:
                        error = 1
            else:
                error = 2    
            #print (uvEdgeOrder)
        else:
            error = 3
            
        if 0 < error:
            bpy.ops.error.message('INVOKE_DEFAULT', message = "Something wrong, maybe single line couldn't found")   
        else:
            nonManifold = (0 < len(uvEdgeOrder[1]))
            uv = [0,0]
            uv_old = [0,0]
            w0 = uv_layer[uvEdgeOrder[0][-1]].uv - uv_layer[uvEdgeOrder[0][0]].uv
            if nonManifold:
                w1 = uv_layer[uvEdgeOrder[1][-1]].uv - uv_layer[uvEdgeOrder[1][0]].uv
            d = (me.vertices[vertsOrder[0]].co - me.vertices[vertsOrder[1]].co).length
            for i in range(1,len(vertsOrder) - 1):
                #print ("---" , i, uvEdgeOrder[0][i], uvEdgeOrder[1][i])
                ratiod = d / dist
                d += (me.vertices[vertsOrder[i]].co - me.vertices[vertsOrder[i+1]].co).length
                uv_old[0] = verts2uv[uvEdgeOrder[0][i]][1]
                uv[0] = uv_layer[uvEdgeOrder[0][0]].uv + w0*ratiod
                c = 1
                if nonManifold:
                    uv_old[1] = verts2uv[uvEdgeOrder[1][i]][1]
                    uv[1] = uv_layer[uvEdgeOrder[1][0]].uv + w1*ratiod
                    c = 2
                for j in range(c):
                    for uvi in markedUV:
                        #print ('+',uvi, verts2uv[uvi][0], verts2uv[uvEdgeOrder[j][i]][0], verts2uv[uvi][1], uv_old[j])
                        if verts2uv[uvEdgeOrder[j][i]] == verts2uv[uvi] and (verts2uv[uvi][1] - uv_old[j]).length < 1e-7:
                            #print (uvi, uv_layer[uvi].uv)
                            uv_layer[uvi].uv = uv[j]
        #print ("len(markedUV)", len(markedUV))
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}
    
class UVRound(bpy.types.Operator):
    '''uv round'''
    bl_idname = 'uv.round'
    bl_label = 'uvround'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active = bpy.context.active_object
        bpy.ops.object.mode_set(mode='OBJECT')
        interval = int(context.scene.uv_interval)
        me = active.data
        uv_layer = me.uv_layers.active.data
        for face in me.polygons:
            for i in range(len(face.loop_indices)):
                iv = face.vertices[i]
                v = me.vertices[iv]
                if v.select:
                    uv = uv_layer[face.loop_indices[i]].uv
                    #print (i,iv, face.loop_indices[i], uv.x, uv.y)
                    uv.x = round(interval * uv.x) / interval
                    uv.y = round(interval * uv.y) / interval
            
        bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}
            
    

class VIEW3D_PT_tools_UVTest(bpy.types.Panel):
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_idname = 'uv_even'

    bl_label = "uv align raster"
    bl_context = "objectmode"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        active_obj = context.active_object
        layout = self.layout

        colm = layout.column(align=True)
        col = colm.column(align=True)
        col.operator("uv.linealign", text="Line align")
        
        colm = layout.column(align=True)
        
        row = colm.split(0.25)
        #row.split = 0.15
        w = row.prop(context.scene, "uv_interval")
        #row.split(percentage=0.15)
        #w.alignment = 'RIGHT'
        row.operator("uv.round", text="Round")

        #col = colm.column(align=True)
        #col.operator("uv.linealign", text="Round")

classes = [MessageOperator, OkOperator,
    UVTest,
    UVRound,
    VIEW3D_PT_tools_UVTest]   
                    
def register():
    #bpy.utils.register_module(__name__)
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.uv_interval = EnumProperty(
		name="",
		description="uv rounding factor",
		items=[("256","1","1"),
			   ("128","2","2"),
			   ("64","4","4"),
			   ("32","8","8"),
			   ("16","16","16"),
			   ("8","32","32"),
			  ],
		default='16')
   
def unregister():
    #bpy.utils.unregister_module(__name__)
    for c in classes:
        bpy.utils.unregister_class(c)
   
if __name__ == "__main__":
    register()   