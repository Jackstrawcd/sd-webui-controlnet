import os
from modules import shared

models_path = shared.opts.data.get('control_net_modules_path', None)
if not models_path:
    models_path = getattr(shared.cmd_opts, 'controlnet_annotator_models_path', None)
if os.path.isdir('models/ControlNetAnnotator'):
    models_path = 'models/ControlNetAnnotator'
if os.path.isdir('/data/apksamba/sd/models/ControlNetAnnotator'):
    models_path = '/data/apksamba/sd/models/ControlNetAnnotator'
if not models_path:
    models_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
if os.path.isdir('models/ControlNetAnnotator/clip_vision'):
    clip_vision_path = 'models/ControlNetAnnotator/clip_vision'
elif os.path.isdir('/data/apksamba/sd/models/ControlNetAnnotator/clip_vision'):
    clip_vision_path = '/data/apksamba/sd/models/ControlNetAnnotator/clip_vision'
else:
    clip_vision_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clip_vision')
# clip vision is always inside controlnet "extensions\sd-webui-controlnet"
# and any problem can be solved by removing controlnet and reinstall

models_path = os.path.realpath(models_path)
os.makedirs(models_path, exist_ok=True)
print(f'ControlNet preprocessor location: {models_path}')
# Make sure that the default location is inside controlnet "extensions\sd-webui-controlnet"
# so that any problem can be solved by removing controlnet and reinstall
# if users do not change configs on their own (otherwise users will know what is wrong)
