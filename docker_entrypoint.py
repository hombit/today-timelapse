#!/usr/bin/env python3

import argparse
import logging
import os
from contextlib import AbstractContextManager, contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from subprocess import check_call
from tempfile import TemporaryDirectory
from time import sleep
from typing import Optional

import schedule


@contextmanager
def nullcontext(x):
    """contextlib.nullcontext was added in Python 3.7"""
    try:
        yield x
    finally:
        pass


def get_video_path(parent_dir: Path) -> Path:
    dt = datetime.now() - timedelta(hours=6)
    dir_name = dt.strftime('%Y%m%d%p')
    dir_path = parent_dir.joinpath(dir_name)
    if not dir_path.exists():
        raise FileNotFoundError("{} doesn't exist".format(dir_path))
    return dir_path


def output_dir_context(path: Optional[Path], tmp_path: Optional[Path] = None) -> AbstractContextManager:
    if path is not None:
        return nullcontext(str(path))
    return TemporaryDirectory(dir=tmp_path)


def create_timelapse(input_dir: Path, output_file: Path, tmp_path: Optional[Path] = None):
    logging.info('Start to process dir {}'.format(input_dir))
    with TemporaryDirectory(dir=tmp_path) as img_dir:
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


class _YouTubeUploader:
    _default_config_root = Path('/')

    def __init__(self, config_root=_default_config_root):
        from base64 import b64decode

        self.config_root = config_root

        self.secrets_path = config_root.joinpath('secrets.json')
        with self.secrets_path.open('wb') as fh:
            fh.write(b64decode(os.environb[b'SECRETS_JSON']))

        self.credentials_path = config_root.joinpath('credentials.json')
        with self.credentials_path.open('wb') as fh:
            fh.write(b64decode(os.environb[b'CREDENTIALS_JSON']))

    def upload(self, fpath: Path) -> None:
        from youtube_video_upload.upload_from_options import upload_from_options

        upload_from_options(dict(
            videos=[dict(
                title=fpath.name,
                file=str(fpath),
                privacy='private',
            )],
            secrets_path=self.secrets_path,
            credentials_path=self.credentials_path,
        ))


class YouTubeUploader(_YouTubeUploader):
    obj = None

    def __new__(cls, *args, **kwargs):
        if cls.obj is None:
            cls.obj = super().__new__(cls, *args, **kwargs)
        return cls.obj


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument('dir', nargs='+', type=Path, help='Example: /bluepi')
    parser.add_argument('--tmp-path', default=None, type=Path, help='dir for temp images')
    parser.add_argument('--now', action='store_true', help='run once only')
    parser.add_argument('--output', default=None, type=Path, help='output dir, default no output')
    parser.add_argument('--upload', action='store_true', help='upload to YouTube')
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
        output_name = '{}-{}.mp4'.format(d.name, video_dir.name)
        with output_dir_context(args.output, tmp_path=tmp_path) as output_dir:
            output_dir = Path(output_dir)
            output_path = output_dir.joinpath(output_name)
            create_timelapse(video_dir, output_path, tmp_path=tmp_path)
            if args.upload:
                try:
                    YouTubeUploader().upload(output_path)
                    logging.info('{} is uploaded to YouTube'.format(output_path))
                except Exception as e:
                    logging.error(str(e))


def main():
    logging.basicConfig(level=logging.INFO)

    args = parse_args()
    if args.upload is None and args.output is None:
        raise RuntimeError('Specify --upload or --output or both')

    if args.tmp_path is not None:
        os.makedirs(args.tmp_path, exist_ok=True)
    if args.output is not None:
        os.makedirs(args.output, exist_ok=True)

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
