#!/usr/bin/env python3

import argparse
import logging
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import check_call
from time import sleep
from typing import Optional

import schedule


def get_video_path(parent_dir: Path) -> Path:
    dt = datetime.now() - timedelta(hours=6)
    dir_name = dt.strftime('%Y%m%d%p')
    dir_path = parent_dir.joinpath(dir_name)
    if not dir_path.exists():
        raise FileNotFoundError("{} doesn't exist".format(dir_path))
    return dir_path


def create_timelapse(input_dir: Path, output_file: Path, tmp_path: Optional[Path]=None):
    logging.info('Start to process dir {}'.format(input_dir))
    with tempfile.TemporaryDirectory(dir=tmp_path) as img_dir:
        file_names = sorted(f for f in os.listdir(input_dir) if f.endswith('.mp4'))
        for fname in file_names:
            cmd = [
                'ffmpeg',
                '-hwaccel', 'vaapi',
                '-vaapi_device', '/dev/dri/renderD128',
                '-i', input_dir.joinpath(fname),
                '-vf', 'fps=0.04,format=nv12,hwupload',
                '-c:v', 'mjpeg_vaapi',
                '-global_quality', '90',
                '-f', 'image2',
                '-y',
                os.path.join(img_dir, fname + '_%05d.jpeg')
            ]
            check_call(cmd)
        cmd = [
            'ffmpeg',
            '-hwaccel', 'vaapi',
            '-vaapi_device', '/dev/dri/renderD128',
            '-pattern_type', 'glob',
            '-i', os.path.join(img_dir, '*.jpeg'),
            '-vf', 'fps=60,format=nv12,hwupload',
            '-c:v', 'h264_vaapi',
            '-y',
            str(output_file)
        ]
        check_call(cmd)
        logging.info('File {} is created'.format(output_file))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', nargs='+', type=Path, help='Example: /bluepi')
    parser.add_argument('--tmp-path', default=None, type=Path, help='dir for temp images')
    parser.add_argument('--now', action='store_true', help='run once only')
    args = parser.parse_args()
    return args


def job():
    args = parse_args()
    dirs = args.dir
    tmp_path = args.tmp_path

    for d in dirs:
        try:
            video_dir = get_video_path(d)
        except FileNotFoundError as e:
            logging.warning(str(e))
            continue
        output_name = '{}_{}.mp4'.format(d.name, video_dir.name)
        output_path = Path('/output').joinpath(output_name)
        create_timelapse(video_dir, output_path, tmp_path=tmp_path)


def main():
    logging.basicConfig(level=logging.DEBUG)

    args = parse_args()

    if args.tmp_path is not None:
        os.makedirs(args.tmp_path)

    if args.now:
        job()
        return

    schedule.every().day.at("01:00").do(job)
    schedule.every().day.at("13:00").do(job)
    while True:
        schedule.run_pending()
        sleep(1)


if __name__ == '__main__':
    main()
