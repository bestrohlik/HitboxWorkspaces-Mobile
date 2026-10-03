[app]
title = Hitbox Workspaces
package.name = hitboxworkspaces
package.domain = org.hitbox
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = .github,bin,.buildozer,venv,__pycache__
version = 1.0
requirements = python3,kivy==2.3.0,plyer,pyjnius,android
orientation = portrait
fullscreen = 0

# Android
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True

[buildozer]
log_level = 2
warn_on_root = 1
