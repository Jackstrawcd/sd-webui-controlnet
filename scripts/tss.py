#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time    : 2023/8/23 11:07 AM
# @Author  : wangdongming
# @Site    : 
# @File    : tss.py
# @Software: Hifive
import time
import typing
import os
import uuid
import warnings

import requests
from PIL import Image
from io import BytesIO
from modules.shared import opts, cmd_opts
from scripts import global_state
from urllib.parse import urlparse
from enum import IntEnum

HOST = os.getenv('TSS_HOST', 'https://draw-plus-backend-qa.xingzheai.cn/').rstrip('/')
BUCKET = getattr(opts, "xz_bucket", os.getenv('StorageBucket', 'xingzheaidraw'))
TSS_CODE_OK = 200
cache = {}


class TaskStatus(IntEnum):
    Waiting = 0
    Prepare = 1
    Ready = 2
    Running = 3
    Uploading = 4
    TrainCompleted = 9
    Finish = 10
    Failed = -1


def enable():
    is_worker = cmd_opts.worker
    return getattr(opts, "xz_ext_enable", False) and not is_worker


def get_tushuashua_token():
    if hasattr(opts, "tu-token"):

        t = getattr(opts, "tu-token")
        if time.time() > t['expire'] - 60:
            return ''
        token = str(t['token'])
        if not token.startswith('Bearer'):
            token = f'Bearer {t["token"]}'
        return token
    return ''


def request_tss(api) -> typing.Optional[typing.Any]:
    headers = {
        'Authorization': get_tushuashua_token(),
        'User-Agent': 'SD separation edition'
    }
    resp = requests.get(api, headers=headers, timeout=5)
    if resp:
        json_d = resp.json()
        if json_d['code'] == TSS_CODE_OK:
            return json_d['data']


def request_mudules():
    warnings.warn('Call to deprecated function: request_mudules', DeprecationWarning)
    api = HOST + '/v1/samplers/category?categorys=3'
    data = request_tss(api)
    if not data:
        data = cache.get('mudules')
    else:
        cache['mudules'] = data

    if not data:
        raise Exception('request tss failed')
    return [item['real_value'] for item in data['items']['3']]


def request_preprocess_v2():
    api = HOST + '/v1/controlnet/preprocessor?limit=200'
    data = request_tss(api)
    if not data:
        data = cache.get('mudules')
    else:
        cache['mudules'] = data

    if not data:
        raise Exception('request tss failed')

    processors = set()
    models = {"None": None}
    for item in data['items']:
        p = item['preprocessor']
        if p == 'None':
            p = 'none'
        processors.add(p)
        if '无' != item['model_name']:
            models[item['model_name']] = models[item['model']]

    return list(processors), models


def request_models():
    warnings.warn('Call to deprecated function: request_models', DeprecationWarning)
    api = HOST + '/v1/samplers/category?categorys=4'
    data = request_tss(api)
    if not data:
        data = cache.get('models')
    else:
        cache['models'] = data

    if not data:
        raise Exception('request tss failed')
    d = dict((item['display_value'], item['real_value']) for item in data['items']['4'])
    if '无' in d:
        del d['无']
    d.update({"None": None})
    return d


def set_ui_preprocessors(tss):
    global_state.ui_preprocessor_keys.clear()
    warnings.warn('Call to deprecated function: set_ui_preprocessors', DeprecationWarning)
    if tss:
        tss_processors = request_mudules()
        for p in tss_processors:
            if p == 'None':
                p = 'none'
            global_state.ui_preprocessor_keys.append(p)
    else:

        global_state.ui_preprocessor_keys.extend(['none', global_state.preprocessor_aliases['invert']])
        global_state.ui_preprocessor_keys += sorted([global_state.preprocessor_aliases.get(k, k)
                                                     for k in global_state.cn_preprocessor_modules.keys()
                                                     if global_state.preprocessor_aliases.get(k, k)
                                                     not in global_state.ui_preprocessor_keys])


def set_ui_preprocess_model_v2(tss):
    global_state.ui_preprocessor_keys.clear()

    if tss:
        tss_processors, models = request_preprocess_v2()
        global_state.cn_models.clear()
        global_state.cn_models.update(models)
        global_state.ui_preprocessor_keys.extend(tss_processors)

    else:
        global_state.update_cn_models()
        global_state.ui_preprocessor_keys.extend(['none', global_state.preprocessor_aliases['invert']])
        global_state.ui_preprocessor_keys += sorted([global_state.preprocessor_aliases.get(k, k)
                                                     for k in global_state.cn_preprocessor_modules.keys()
                                                     if global_state.preprocessor_aliases.get(k, k)
                                                     not in global_state.ui_preprocessor_keys])


def set_ui_models(tss):
    warnings.warn('Call to deprecated function: set_ui_models', DeprecationWarning)
    if not tss:
        global_state.update_cn_models()
    else:
        global_state.cn_models.clear()
        models = request_models()
        global_state.cn_models.update(models)


def init_tss_ui():
    if enable() and not cache.get('init', 0):
        print('request tss controlnet preprocess and models...')
        set_ui_preprocess_model_v2(True)
        cache['init'] = 1


def preprocess_hooker():
    #
    # cache['ui_preprocessor_keys'] = [x for x in global_state.ui_preprocessor_keys]
    callbacks = getattr(opts, 'xz_ext_callbacks', []) or []

    # callbacks.append(set_ui_preprocessors)
    # callbacks.append(set_ui_models)
    callbacks.append(set_ui_preprocess_model_v2)
    setattr(opts, 'xz_ext_callbacks', callbacks)


def headers():
    return {
        "Content-Type": "application/json",
        "Authorization": get_tushuashua_token()
    }


def upload_image_data(image_data: Image, persistent=False):
    filename = f'{uuid.uuid4()}.png'

    with BytesIO() as output_bytes:
        image_data.save(output_bytes, format="PNG")
        bytes_data = output_bytes.getvalue()
        data = {
            'filename': filename,
            'file_size': len(bytes_data),
            'persistent': persistent
        }

        resp = requests.post(HOST + '/v1/oss-files', json=data, timeout=4, headers=headers())
        if resp:
            json_d = resp.json()
            if json_d['code'] == TSS_CODE_OK:
                data = json_d['data']
                resp2 = requests.put(data['url'], headers={
                    'Content-Type': 'image/png'
                }, data=bytes_data)
                if resp2:
                    return data['oss_key']
                else:
                    print(resp2.text)
            else:
                print(resp.text)


def waite_task(task_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(2)
        resp = requests.get(HOST + f'/v1/img-tasks/{task_id}', headers=headers(), timeout=5)
        if resp:
            json_d = resp.json()
            if json_d['code'] == TSS_CODE_OK:
                data = json_d['data']
                status = data['status']
                if status == TaskStatus.Failed or status == TaskStatus.Finish:
                    return data


def run_annotator(image, module, pres, pthr_a, pthr_b, t2i_w, t2i_h, pp, rm):
    # upload image
    image_key = upload_image_data(Image.fromarray(image['image']))
    mask_key = upload_image_data(Image.fromarray(image['mask']))

    if not image_key or not mask_key:
        print("upload image file failed")
        raise Exception('upload image file failed')

    data = {
        'image': os.path.join(BUCKET, image_key),
        'mask': os.path.join(BUCKET, mask_key),
        'module': module,
        'annotator_resolution': pres,
        'pthr_a': pthr_a,
        'pthr_b': pthr_b,
        't2i_w': t2i_w,
        't2i_h': t2i_h,
        'pp': pp,
        'rm': rm,
        'user_id': 'SD-PLUS-'
    }
    resp = requests.post(HOST + '/v1/img2img-tasks/cnet', json=data, timeout=4, headers=headers())
    if resp:
        json_d = resp.json()
        if json_d['code'] == TSS_CODE_OK:
            res = waite_task(json_d['data']['task_id'])
            if res:
                images = res.get('hig_images') or res.get('images')
                if images:
                    image_url = images[0]
                    resp = requests.get(image_url, timeout=10)
                    if resp:
                        pr = urlparse(image_url)
                        if not pr.path:
                            print(f"cannot get image name:{image_url}")
                            return ''

                        filename = os.path.join('tmp', os.path.basename(pr.path))
                        with open(filename, "wb+") as f:
                            f.write(resp.content)

                        return filename
                elif res.get('desc'):
                    raise OSError(res.get('desc'))


preprocess_hooker()
