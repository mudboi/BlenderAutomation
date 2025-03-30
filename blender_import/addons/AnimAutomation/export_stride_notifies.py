
import bpy
import addon_utils
import os.path
import importlib
import blender_auto_common
import xml.etree.ElementTree as et


class ExportStrideNotifies(bpy.types.Operator):
    """Export local pose markers for all actions in all strips for currently selected NLA tracks into an XML file that
    can then be imported into unreal engine to populate stride notifies and sync markers in the corresponding
    animation asset for each action.

    USER NOTES:
      1) Pose Markers need to be named exactly how you want them named in unreal, case sensitive. THEY MUST BE
        NAMED [FOOT DESIGNATOR][_Down/_Up] where FOOT_DESIGNATOR is like LF or RF. If they are not named with th
        _Down/_Up suffix, will be ignored
      2) REQUIRES SEND2UE PLUGIN, uses that plugin export paths to as the path to save the xml files, so when
        exporting animations into unreal using Send2UE, this operator will place corresponding stride notifies xml
        at that same location of the animation uasset
      3) Run operator defined below, by going to PIPELINE HEADER MENU > EXPORT"""

    bl_idname = "wm.export_stride_notifies"  # How to ref class from blender python
    bl_label = "Export Stride Notifies"  # Name in operator menu
    bl_options = {'REGISTER', 'UNDO'}  # Registers and enables undo

    def execute(self, context):
        rig_obj = blender_auto_common.find_object_in_mode('POSE', context=context)
        xml_export_path = self.get_xml_path(context)
        print("Exporting Stride Notifies to: " + xml_export_path)
        for track in rig_obj.animation_data.nla_tracks:
            if not track.select:
                continue
            for strip in track.strips:
                if not strip.action:
                    print("    Skipping strip '" + strip.name + "', no action is linked to it")
                    continue
                self.write_xml_file(strip.action, xml_export_path)

        return {'FINISHED'}

    @staticmethod
    def get_xml_path(context):
        # import unreal module from send2ue's dependencies folder
        send2ue_mod = next(m for m in addon_utils.modules() if m.__name__ == "send2ue")
        send2ue_dep_path = os.path.join(os.path.dirname(send2ue_mod.__file__), "dependencies")
        unreal = importlib.machinery.SourceFileLoader('unreal', os.path.join(send2ue_dep_path, 'unreal.py')).load_module()
        # run unreal.Paths.project_content_dir() in currently running unreal instance remote python server to get project
        # content dir path for currently running project
        if not unreal.is_connected():
            raise Exception("Could not connect to a running Unreal Engine Instance")
        unreal_content_path = unreal.run_commands(
            ['print(os.path.abspath(os.path.join(os.getcwd(), unreal.Paths.project_content_dir())))'])
        unreal_content_path = unreal_content_path.replace("\r\n", "")
        anim_export_path = context.scene.send2ue.unreal_animation_folder_path.replace('/Game/', '')
        return os.path.abspath(os.path.join(unreal_content_path, anim_export_path))

    @staticmethod
    def write_xml_file(action, filepath):
        filename = "stride_notifies" + action.name + ".xml"
        stride_notifies = {}
        for m in action.pose_markers:
            if "_Down" in m.name or "_Up" in m.name:
                stride_notifies[m.name] = m.frame
        if len(stride_notifies) == 0:
            print("    Skipping action: " + action.name + ", does not have any stride notifies")
            return
        else:
            print("    " + action.name + ": " + str(stride_notifies))
        root = et.Element("stride_notifies")
        for n, f in stride_notifies.items():
            sub = et.SubElement(root, n)
            sub.text = str(f)
        tree = et.ElementTree(root)
        et.indent(tree, space="\t", level=0)
        tree.write(os.path.join(filepath, filename), encoding="utf-8", xml_declaration=True)


def add_pipeline_export_menu_item(self, _):
    self.layout.operator(ExportStrideNotifies.bl_idname)


def register():
    """Registers this add-on to blender if user selected (called by blender)"""
    send2ue_enabled = addon_utils.enable('send2ue')
    if send2ue_enabled:
        bpy.utils.register_class(ExportStrideNotifies)
        # add Pipeline > Export menu item
        bpy.types.TOPBAR_MT_Export.append(add_pipeline_export_menu_item)
    else:
        print("Could not load operator " + ExportStrideNotifies.bl_label + " as Send2UE is not enabled")

def unregister():
    """Unregisters this add-on is user de-selected"""
    bpy.utils.unregister_class(ExportStrideNotifies)
    bpy.types.TOPBAR_MT_Export.remove(add_pipeline_export_menu_item)


if __name__ == '__main__':
    register()
