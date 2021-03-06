#!/usr/bin/env python
#
# zip up the titanium mobile SDKs into suitable distribution formats
#
import os, types, glob, shutil, sys, platform, codecs
import zipfile, datetime, subprocess, tempfile, time

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(sys._getframe(0).f_code.co_filename)),'..','support','common'))
import simplejson

if platform.system() == 'Darwin':
	import importresolver

packaging_all = False
os_names = { "Windows":"win32", "Linux":"linux", "Darwin":"osx" }
cur_dir = os.path.abspath(os.path.dirname(sys._getframe(0).f_code.co_filename))
top_dir = os.path.abspath(os.path.join(os.path.dirname(sys._getframe(0).f_code.co_filename),'..'))
template_dir = os.path.join(top_dir,'support')
doc_dir = os.path.abspath(os.path.join(top_dir, 'apidoc'))
all_dir = os.path.abspath(os.path.join(template_dir,'all'))
android_dir = os.path.abspath(os.path.join(template_dir,'android'))
iphone_dir = os.path.abspath(os.path.join(template_dir,'iphone'))
osx_dir = os.path.abspath(os.path.join(template_dir,'osx'))
win32_dir = os.path.abspath(os.path.join(template_dir, 'win32'))
mobileweb_dir = os.path.abspath(os.path.join(template_dir, 'mobileweb'))
blackberry_dir = os.path.abspath(os.path.join(template_dir, 'blackberry'))
tizen_dir = os.path.abspath(os.path.join(template_dir, 'tizen'))
windows_dir = os.path.abspath(os.path.join(template_dir, 'windows'))
ivi_dir = os.path.abspath(os.path.join(template_dir, 'ivi'))

buildtime = datetime.datetime.now()
ts = buildtime.strftime("%m/%d/%y %H:%M")

# get the githash for the build so we can always pull this build from a specific
# commit
gitCmd = "git"
if platform.system() == "Windows":
	gitCmd += ".cmd"

p = subprocess.Popen([gitCmd,"show","--abbrev-commit","--no-color"],stderr=subprocess.PIPE, stdout=subprocess.PIPE)
githash = p.communicate()[0][7:].split('\n')[0].strip()

ignoreExtensions = ['.pbxuser','.perspectivev3','.pyc']
ignoreDirs = ['.DS_Store','.git','.gitignore','libTitanium.a','titanium.jar','bridge.txt', 'packaged']

def remove_existing_zips(dist_dir, version_tag):
	for os_name in os_names.values():
		filename = os.path.join(dist_dir,
				'mobilesdk-%s-%s.zip' % (version_tag, os_name))
		if os.path.exists(filename):
			os.remove(filename)

def ignore(file):
	 for f in ignoreDirs:
		if file == f:
			return True
	 return False

def generate_jsca():
	 process_args = [sys.executable, os.path.join(doc_dir, 'docgen.py'), '-f', 'jsca', '--stdout']
	 print "Generating JSCA..."
	 print " ".join(process_args)
	 jsca_temp_file = tempfile.TemporaryFile()
	 try:
		 process = subprocess.Popen(process_args, stdout=jsca_temp_file, stderr=subprocess.PIPE)
		 process_return_code = process.wait()
		 if process_return_code != 0:
			 err_output = process.stderr.read()
			 print >> sys.stderr, "Failed to generate JSCA JSON.  Output:"
			 print >> sys.stderr, err_output
			 return None
		 jsca_temp_file.seek(0)
		 jsca_json = jsca_temp_file.read()
		 return jsca_json
	 finally:
		 jsca_temp_file.close()

def zip_dir(zf,dir,basepath,subs=None,cb=None, ignore_paths=None, ignore_files=None):
	for root, dirs, files in os.walk(dir):
		for name in ignoreDirs:
			if name in dirs:
				dirs.remove(name)	# don't visit ignored directories
		for file in files:
			skip = False
			if ignore_paths != None:
				for p in ignore_paths:
					if root.startswith(p):
						skip = True
						continue
			from_ = os.path.join(root, file)
			if skip or (ignore_files != None and from_ in ignore_files):
				continue
			e = os.path.splitext(file)
			if len(e)==2 and e[1] in ignoreExtensions: continue
			to_ = from_.replace(dir, basepath, 1)
			if subs!=None:
				c = open(from_).read()
				for key in subs:
					c = c.replace(key,subs[key])
				if cb!=None:
					c = cb(file,e[1],c)
				zf.writestr(to_,c)
			else:
				zf.write(from_, to_)

def zip2zip(src_zip, dest_zip, prepend_path=None):
	for zinfo in src_zip.infolist():
		f = src_zip.open(zinfo)
		new_name = zinfo.filename
		if prepend_path and not prepend_path.endswith("/"):
			prepend_path = "%s/" % prepend_path
		if prepend_path:
			new_name = "%s%s" % (prepend_path, new_name)
		zinfo.filename = new_name
		dest_zip.writestr(zinfo, f.read())

def zip_packaged_modules(zf, source_dir, iphone=False):
	print "Zipping packaged modules..."
	for root, dirs, files in os.walk(source_dir):
		for name in ignoreDirs:
			if name in dirs:
				dirs.remove(name)
		for fname in files:
			if not fname.lower().endswith(".zip") or (not iphone and "iphone" in fname.lower()):
				continue
			source_zip = zipfile.ZipFile(os.path.join(root, fname), "r")
			rel_path = root.replace(source_dir, "").replace("\\", "/")
			if rel_path.startswith("/"):
				rel_path = rel_path[1:]
			try:
				zip2zip(source_zip, zf, rel_path)
			finally:
				source_zip.close()

def zip_android(zf, basepath, version):
	print "Zipping Android platform..."
	android_dist_dir = os.path.join(top_dir, 'dist', 'android')

	for jar in ['titanium.jar', 'kroll-apt.jar', 'kroll-common.jar', 'kroll-v8.jar']:
		jar_path = os.path.join(android_dist_dir, jar)
		zf.write(jar_path, '%s/android/%s' % (basepath, jar))

	zip_dir(zf, os.path.join(top_dir, 'android', 'cli'), basepath+'/android/cli')
	zip_dir(zf, os.path.join(top_dir, 'android', 'templates'), basepath+'/android/templates')

	# include headers for v8 3rd party module building
	def add_headers(dir):
		for header in os.listdir(dir):
			if not header.endswith('.h'):
				continue
			header_path = os.path.join(dir, header)
			zf.write(header_path, '%s/android/native/include/%s' % (basepath, header))

	android_runtime_dir = os.path.join(top_dir, 'android', 'runtime')
	android_runtime_v8_dir = os.path.join(android_runtime_dir, 'v8')

	v8_src_native_dir = os.path.join(android_runtime_v8_dir, 'src', 'native')
	add_headers(v8_src_native_dir)

	v8_gen_dir = os.path.join(android_runtime_v8_dir, 'generated')
	add_headers(v8_gen_dir)

	import ant
	libv8_properties = ant.read_properties(open(os.path.join(top_dir, 'android', 'build', 'libv8.properties')))
	libv8_version = libv8_properties['libv8.version']
	libv8_mode = libv8_properties['libv8.mode']

	v8_include_dir = os.path.join(android_dist_dir, 'libv8', libv8_version, libv8_mode, 'include')
	add_headers(v8_include_dir)

	# add js2c.py for js -> C embedding
	js2c_py = os.path.join(android_runtime_v8_dir, 'tools', 'js2c.py')
	jsmin_py = os.path.join(android_runtime_v8_dir, 'tools', 'jsmin.py')
	zf.write(js2c_py, '%s/module/android/js2c.py' % basepath)
	zf.write(jsmin_py, '%s/module/android/jsmin.py' % basepath)

	# include all native shared libraries
	libs_dir = os.path.join(android_dist_dir, 'libs')
	for lib_dir in os.listdir(libs_dir):
		arch_dir = os.path.join(libs_dir, lib_dir)
		for so_file in os.listdir(arch_dir):
			if so_file.endswith('.so'):
				so_path = os.path.join(arch_dir, so_file)
				zf.write(so_path, '%s/android/native/libs/%s/%s' % (basepath, lib_dir, so_file))

	ant_tasks_jar = os.path.join(android_dist_dir, 'ant-tasks.jar')
	zf.write(ant_tasks_jar, '%s/module/android/ant-tasks.jar' % basepath)

	ant_contrib_jar = os.path.join(top_dir, 'android', 'build', 'lib', 'ant-contrib-1.0b3.jar')
	zf.write(ant_contrib_jar, '%s/module/android/ant-contrib-1.0b3.jar' % basepath)

	kroll_apt_lib_dir = os.path.join(top_dir, 'android', 'kroll-apt', 'lib')
	for jar in os.listdir(kroll_apt_lib_dir):
		if jar.endswith('.jar'):
			jar_path = os.path.join(kroll_apt_lib_dir, jar)
			zf.write(jar_path, '%s/android/%s' % (basepath, jar))

	android_depends = os.path.join(top_dir, 'android', 'dependency.json')
	zf.write(android_depends, '%s/android/dependency.json' % basepath)

	android_modules = os.path.join(android_dist_dir, 'modules.json')
	zf.write(android_modules, '%s/android/modules.json' % basepath)

	zf.writestr('%s/android/package.json' % basepath, codecs.open(os.path.join(top_dir, 'android', 'package.json'), 'r', 'utf-8').read().replace('__VERSION__', version))

	titanium_lib_dir = os.path.join(top_dir, 'android', 'titanium', 'lib')
	for thirdparty_jar in os.listdir(titanium_lib_dir):
		if thirdparty_jar == "commons-logging-1.1.1.jar": continue
		jar_path = os.path.join(top_dir, 'android', 'titanium', 'lib', thirdparty_jar)
		zf.write(jar_path, '%s/android/%s' % (basepath, thirdparty_jar))

	# include all module lib dependencies
	modules_dir = os.path.join(top_dir, 'android', 'modules')
	for module_dir in os.listdir(modules_dir):
		module_lib_dir = os.path.join(modules_dir, module_dir, 'lib')
		if os.path.exists(module_lib_dir):
			for thirdparty_jar in os.listdir(module_lib_dir):
				if thirdparty_jar.endswith('.jar'):
					jar_path = os.path.join(module_lib_dir, thirdparty_jar)
					zf.write(jar_path, '%s/android/%s' % (basepath, thirdparty_jar))

	android_module_jars = glob.glob(os.path.join(android_dist_dir, 'titanium-*.jar'))
	for android_module_jar in android_module_jars:
		 jarname = os.path.split(android_module_jar)[1]
		 zf.write(android_module_jar, '%s/android/modules/%s' % (basepath, jarname))

	android_module_res_zips = glob.glob(os.path.join(android_dist_dir, 'titanium-*.res.zip'))
	for android_module_res_zip in android_module_res_zips:
		zipname = os.path.split(android_module_res_zip)[1]
		zf.write(android_module_res_zip, '%s/android/modules/%s' % (basepath, zipname))

	android_module_res_packages = glob.glob(os.path.join(android_dist_dir, 'titanium-*.respackage'))
	for android_module_res_package in android_module_res_packages:
		packagename = os.path.split(android_module_res_package)[1]
		zf.write(android_module_res_package, '%s/android/modules/%s' % (basepath, packagename))

def resolve_source_imports(platform):
	sys.path.append(iphone_dir)
	import run,prereq
	return importresolver.resolve_source_imports(os.path.join(top_dir,platform,'Classes'))

def make_symbol(fn):
	if fn.startswith('TI') and fn!='TITANIUM' and fn!='TI':
		return fn[2:]
	return fn

def zip_iphone_ipad(zf,basepath,platform,version,version_tag):
	print "Zipping iOS platform..."
#	zf.writestr('%s/iphone/imports.json'%basepath,resolve_source_imports(platform))

	# include our headers such that 3rd party modules can be compiled
	headers_dir=os.path.join(top_dir,'iphone','Classes')
	for f in os.listdir(headers_dir):
		path = os.path.join(headers_dir,f)
		if os.path.isfile(path) and os.path.splitext(f)[1]=='.h':
			 zf.write(path,'%s/iphone/include/%s' % (basepath,f))
		elif os.path.isdir(path):
			for df in os.listdir(path):
				dfpath = os.path.join(headers_dir,f,df)
				if os.path.isfile(dfpath) and os.path.splitext(df)[1]=='.h':
					 zf.write(dfpath,'%s/iphone/include/%s/%s' % (basepath,f,df))

	tp_headers_dir=os.path.join(top_dir,'iphone','headers','JavaScriptCore')
	for f in os.listdir(tp_headers_dir):
		if os.path.isfile(os.path.join(tp_headers_dir,f)) and os.path.splitext(f)[1]=='.h':
			 zf.write(os.path.join(tp_headers_dir,f),'%s/iphone/include/JavaScriptCore/%s' % (basepath,f))

	subs = {
		"__VERSION__":version,
		"__TIMESTAMP__":ts,
		"__GITHASH__": githash
	}

	# xcode_templates_dir =  os.path.join(top_dir,'iphone','templates','xcode')
	# zip_dir(zf,xcode_templates_dir,basepath+'/iphone/xcode/templates',subs)

	iphone_lib = os.path.join(top_dir,'iphone',platform,'build')

	zip_dir(zf,os.path.join(top_dir,'iphone','Classes'),basepath+'/iphone/Classes',subs)
	zip_dir(zf,os.path.join(top_dir,'iphone','headers'),basepath+'/iphone/headers',subs)
	zip_dir(zf,os.path.join(top_dir,'iphone','iphone'),basepath+'/iphone/iphone',subs)
	zf.write(os.path.join(top_dir, 'iphone', 'AppledocSettings.plist'),'%s/iphone/AppledocSettings.plist'%(basepath))
	zip_dir(zf, os.path.join(top_dir, 'iphone', 'cli'), basepath+'/iphone/cli')
	zip_dir(zf, os.path.join(top_dir, 'iphone', 'templates'), basepath+'/iphone/templates')

	ticore_lib = os.path.join(top_dir,'iphone','lib')

	# during 1.3.3, we added a new lib to a folder that had a .gitignore
	# and we need to manually reset this
	if not os.path.exists(os.path.join(ticore_lib,'libtiverify.a')):
		os.system("git checkout iphone/lib")
		if not os.path.exists(os.path.join(ticore_lib,'libtiverify.a')):
			print "[ERROR] missing libtiverify.a!  make sure you checkout iphone/lib or edit your iphone/.gitignore and remove the lib entry"
			sys.exit(1)

	if not os.path.exists(os.path.join(ticore_lib,'libti_ios_debugger.a')):
		os.system("git checkout iphone/lib")
		if not os.path.exists(os.path.join(ticore_lib,'libti_ios_debugger.a')):
			print "[ERROR] missing libti_ios_debugger.a!  make sure you checkout iphone/lib or edit your iphone/.gitignore and remove the lib entry"
			sys.exit(1)

	if not os.path.exists(os.path.join(ticore_lib,'libTiCore.a')):
		print "[ERROR] missing libTiCore.a!"
		sys.exit(1)

	zf.write(os.path.join(ticore_lib,'libTiCore.a'),'%s/%s/libTiCore.a'%(basepath,platform))
	zf.write(os.path.join(ticore_lib,'libtiverify.a'),'%s/%s/libtiverify.a'%(basepath,platform))
	zf.write(os.path.join(ticore_lib,'libti_ios_debugger.a'),'%s/%s/libti_ios_debugger.a'%(basepath,platform))
	zf.write(os.path.join(ticore_lib,'libti_ios_profiler.a'),'%s/%s/libti_ios_profiler.a'%(basepath,platform))

	zf.writestr('%s/%s/package.json' % (basepath, platform), codecs.open(os.path.join(top_dir, 'iphone', 'package.json'), 'r', 'utf-8').read().replace('__VERSION__', version))

	zip_dir(zf,osx_dir,basepath)

	modules_dir = os.path.join(top_dir,'iphone','Resources','modules')
	for f in os.listdir(modules_dir):
		if os.path.isdir(os.path.join(modules_dir,f)):
			module_images = os.path.join(modules_dir,f)
			if os.path.exists(module_images):
				module_name = f.replace('Module','').lower()
				zip_dir(zf,module_images,'%s/%s/modules/%s/images' % (basepath,platform,module_name))

def zip_mobileweb(zf, basepath, version):
	print "Zipping MobileWeb platform..."
	dir = os.path.join(top_dir, 'mobileweb')

	# for speed, mobileweb has its own zip logic
	for root, dirs, files in os.walk(dir):
		for name in ignoreDirs:
			if name in dirs:
				dirs.remove(name)
		for file in files:
			e = os.path.splitext(file)
			if len(e)==2 and e[1] in ignoreExtensions: continue
			from_ = os.path.join(root, file)
			to_ = from_.replace(dir, os.path.join(basepath,'mobileweb'), 1)
			zf.write(from_, to_)

def zip_blackberry(zf, basepath, version):
	print "Zipping Blackberry platform..."
	dir = os.path.join(top_dir, 'blackberry')

	# for speed, mobileweb has its own zip logic
	for root, dirs, files in os.walk(dir):
		for name in ignoreDirs:
			if name in dirs:
				dirs.remove(name)
		for file in files:
			e = os.path.splitext(file)
			if len(e)==2 and e[1] in ignoreExtensions: continue
			from_ = os.path.join(root, file)
			to_ = from_.replace(dir, os.path.join(basepath,'blackberry'), 1)
			zf.write(from_, to_)

def zip_tizen(zf, basepath, version):
	print "Zipping Tizen platform..."
	dir = os.path.join(top_dir, 'tizen')

	# for speed, mobileweb has its own zip logic
	for root, dirs, files in os.walk(dir):
		for name in ignoreDirs:
			if name in dirs:
				dirs.remove(name)
		for file in files:
			e = os.path.splitext(file)
			if len(e)==2 and e[1] in ignoreExtensions: continue
			from_ = os.path.join(root, file)
			to_ = from_.replace(dir, os.path.join(basepath,'tizen'), 1)
			zf.write(from_, to_)


def zip_windows(zf, basepath, version):
	print "Zipping Windows platform..."
	dir = os.path.join(top_dir, 'windows')

	# for speed, mobileweb has its own zip logic
	for root, dirs, files in os.walk(dir):
		for name in ignoreDirs:
			if name in dirs:
				dirs.remove(name)
		for file in files:
			e = os.path.splitext(file)
			if len(e)==2 and e[1] in ignoreExtensions: continue
			from_ = os.path.join(root, file)
			to_ = from_.replace(dir, os.path.join(basepath,'windows'), 1)
			zf.write(from_, to_)

def zip_ivi(zf, basepath, version):
	print "Zipping IVI platform..."
	dir = os.path.join(top_dir, 'ivi')

	# for speed, mobileweb has its own zip logic
	for root, dirs, files in os.walk(dir):
		for name in ignoreDirs:
			if name in dirs:
				dirs.remove(name)
		for file in files:
			e = os.path.splitext(file)
			if len(e)==2 and e[1] in ignoreExtensions: continue
			from_ = os.path.join(root, file)
			to_ = from_.replace(dir, os.path.join(basepath,'ivi'), 1)
			zf.write(from_, to_)

def create_platform_zip(platform,dist_dir,osname,version,version_tag):
	if not os.path.exists(dist_dir):
		os.makedirs(dist_dir)
	basepath = '%s/%s/%s' % (platform,osname,version_tag)
	sdkzip = os.path.join(dist_dir,'%s-%s-%s.zip' % (platform,version_tag,osname))
	zf = zipfile.ZipFile(sdkzip, 'w', zipfile.ZIP_DEFLATED)
	return (zf, basepath, sdkzip)

def zip_mobilesdk(dist_dir, osname, version, module_apiversion, android, iphone, ipad, mobileweb, blackberry, tizen, windows, ivi, version_tag, build_jsca):
	print "Zipping Mobile SDK..."
	zf, basepath, filename = create_platform_zip('mobilesdk', dist_dir, osname, version, version_tag)

	ignore_paths = []
	if osname == 'win32':
		ignore_paths.append(os.path.join(template_dir, 'iphone'))
		ignore_paths.append(os.path.join(template_dir, 'osx'))
	if osname == 'linux':
		ignore_paths.append(os.path.join(template_dir, 'iphone'))
		ignore_paths.append(os.path.join(template_dir, 'osx'))
		ignore_paths.append(os.path.join(template_dir, 'win32'))
	if osname == 'osx':
		ignore_paths.append(os.path.join(template_dir, 'win32'))

	platforms = []
	for dir in os.listdir(top_dir):
		if dir != 'support' and os.path.isdir(os.path.join(top_dir, dir)) and os.path.isfile(os.path.join(top_dir, dir, 'package.json')):
			# if new platforms are added, be sure to add them to the line below!
			if (dir == 'android' and android) or (osname == "osx" and dir == 'iphone' and (iphone or ipad)) or (dir == 'mobileweb' and mobileweb) or (dir == 'blackberry' and blackberry) or (dir == 'tizen' and tizen) or  (dir == 'windows' and windows) or (dir == 'ivi' and ivi):
				platforms.append(dir)

	# bundle root files
	zf.write(os.path.join(top_dir, 'CREDITS'), '%s/CREDITS' % basepath)
	zf.write(os.path.join(top_dir, 'README.md'), '%s/README.md' % basepath)
	zf.write(os.path.join(top_dir, 'package.json'), '%s/package.json' % basepath)
	zip_dir(zf, os.path.join(top_dir, 'cli'), '%s/cli' % basepath, ignore_paths=ignore_paths)

	ignore_paths.append(os.path.join(top_dir, 'node_modules', '.bin'))
	zip_dir(zf, os.path.join(top_dir, 'node_modules'), '%s/node_modules' % basepath, ignore_paths=ignore_paths)

	manifest_json = '''{
	"name": "%s",
	"version": "%s",
	"moduleAPIVersion": "%s",
	"timestamp": "%s",
	"githash": "%s",
	"platforms": %s
}''' % (version_tag, version, module_apiversion, ts, githash, simplejson.dumps(platforms))
	zf.writestr('%s/manifest.json' % basepath, manifest_json)

	# check if we should build the content assist file
	if build_jsca:
		jsca = generate_jsca()
		if jsca is None:
			# This is fatal. If we were meant to build JSCA
			# but couldn't, then packaging fails.
			# Delete the zip to be sure any build/packaging
			# script that fails to read the exit code
			# will at least not have any zip file.
			zf.close()
			if os.path.exists(filename):
				os.remove(filename)
			# If the script was in the middle of packaging
			# for all platforms, remove zips for all platforms
			# to make it clear that packaging failed (since all
			# platforms get the api.jsca which has just failed.)
			if packaging_all:
				remove_existing_zips(dist_dir, version_tag)
			sys.exit(1)

		zf.writestr('%s/api.jsca' % basepath, jsca)

	# copy the templates folder into the archive
	zip_dir(zf, os.path.join(top_dir, 'templates'), '%s/templates' % basepath, ignore_paths=ignore_paths)

	# the 'node_modules' and 'templates' directories was moved from support to the root of
	# timob and we need to nuke it from the support directory so that it doesn't overwrite
	# these directories that have already been added above
	old_node_modules_path = os.path.join(template_dir, 'node_modules')
	if os.path.exists(old_node_modules_path):
		shutil.rmtree(old_node_modules_path, True)
	old_templates_path = os.path.join(template_dir, 'templates')
	if os.path.exists(old_templates_path):
		shutil.rmtree(old_templates_path, True)

	zip_packaged_modules(zf, os.path.join(template_dir, "module", "packaged"), osname == 'osx')
	#zip_dir(zf, all_dir, basepath)
	zip_dir(zf, template_dir, basepath, ignore_paths=ignore_paths)
	if android: zip_android(zf, basepath, version)
	if (iphone or ipad) and osname == "osx": zip_iphone_ipad(zf,basepath,'iphone',version,version_tag)
	if mobileweb: zip_mobileweb(zf, basepath, version)
	if blackberry: zip_blackberry(zf, basepath, version)
	if tizen: zip_tizen(zf, basepath, version)
	if (windows) and osname == "win32": zip_windows(zf, basepath, basepath)
	if ivi: zip_ivi(zf, basepath, version)
	if osname == 'win32': zip_dir(zf, win32_dir, basepath)

	zf.close()

class Packager(object):
	def __init__(self, build_jsca=1):
		self.build_jsca = build_jsca

	def build(self, dist_dir, version, module_apiversion, android=True, iphone=True, ipad=True, mobileweb=True, blackberry=True, tizen=True, ivi=True, windows=True, version_tag=None):
		if version_tag == None:
			version_tag = version

		zip_mobilesdk(dist_dir, os_names[platform.system()], version, module_apiversion, android, iphone, ipad, mobileweb, blackberry, tizen, windows, ivi, version_tag, self.build_jsca)

	def build_all_platforms(self, dist_dir, version, module_apiversion, android=True, iphone=True, ipad=True, mobileweb=True, blackberry=True, tizen=True, ivi=True, windows=True, version_tag=None):
		global packaging_all
		packaging_all = True

		if version_tag == None:
			version_tag = version

		remove_existing_zips(dist_dir, version_tag)

		for os in os_names.values():
			zip_mobilesdk(dist_dir, os, version, module_apiversion, android, iphone, ipad, mobileweb, blackberry, tizen, windows, ivi, version_tag, self.build_jsca)

if __name__ == '__main__':
	Packager().build(os.path.abspath('../dist'), "1.1.0")
