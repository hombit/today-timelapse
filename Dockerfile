FROM opensuse/leap

RUN zypper --non-interactive install timezone\
    && ln -sf /usr/share/zoneinfo/Europe/Moscow /etc/localtime

RUN . /etc/os-release\
    && zypper --non-interactive addrepo -p199 -f -n packman http://ftp.gwdg.de/pub/linux/misc/packman/suse/openSUSE_Leap_${VERSION_ID}/ packman\
    && zypper --non-interactive --gpg-auto-import-keys in --from=packman --recommends ffmpeg-3 intel-vaapi-driver

RUN zypper --non-interactive in python3-pip
RUN pip3 install ffmpeg-python schedule youtube-video-upload

COPY docker_entrypoint.py /docker_entrypoint.py

ENTRYPOINT ["python3", "/docker_entrypoint.py"]
