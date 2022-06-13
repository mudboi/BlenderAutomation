Blender Automation

Miscellaneous functions, modules, and plugins for making blender easier.

In order to use this repo, Blender needs to know about it, so 

1) Open Blender (3.0) 
2) Go to Edit->Preferences->File Paths
3) Under Data->Scripts type: "{PATH_TO_REPO}\BlenderAutomation\blender_import\" where 
{PATH_TO_REPO} is the absolute path to this repo on your machine
5) Restart Blender

There are three main ways to inject python into blender:

1) Addons (Plugins) which should be placed in  "\blender_import\addons\" directory and can be
enabled in Edit->Preferences->Add-ons. Make add-ons if you have a general automation task 
that needs to run in multiple but not all blender files.

2) Modules which should be placed in "\blender_import\modules\". This is python you want
to expose to blender in-app scripting and for common functionality used between plugins.

3) Startup files, which should be placed in "\blender_import\startup", this should be
python that you want to execute at blender start-up, usually to add some functionality
that you wan't to run for all blender files.

More info on all this can be found here:

https://docs.blender.org/api/current/info_overview.html#:~:text=Python%20in%20Blender&text=Blender%20provides%20its%20Python%20modules,import%20the%20modules%20to%20work.
 