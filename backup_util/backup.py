#!/usr/bin/python

import os
import errno
import sys
import getopt
import time
import datetime
import re
import subprocess
import shutil

local_cleanup_file = None
local_cleanup_file_name = 'local_cleanup.sh'

remote_test_file = None
remote_test_file_name = 'remote_test.sh'

corrupt_pair_file = None
corrupt_pair_file_name = 'corrupt_pairs'

def add_file_to_cleanup(file):
	global local_cleanup_file
	if local_cleanup_file is None:
		local_cleanup_file = open(local_cleanup_file_name,'wx')
		local_cleanup_file.write('#!/bin/sh\n')
	local_cleanup_file.write("rm \"{}\";\n".format(file))

def add_remote_file_to_test(local_file, remote_file):
	global remote_test_file
	if remote_test_file is None:
		remote_test_file = open(remote_test_file_name,'wx')
		remote_test_file.write('#!/bin/sh\n')
	remote_test_file.write("echo \"{}\";\nopen \"{}\";\nopen \"{}\";\nsleep 10;\n".format(remote_file,local_file,remote_file))

def add_corrupt_pair(orig_file, backup_file):
	global corrupt_pair_file
	if corrupt_pair_file is None:
		corrupt_pair_file = open(corrupt_pair_file_name,'wx')
	corrupt_pair_file.write("\"{}\",\"{}\"\n".format(orig_file, backup_file))

def check_for_remote_duplicates(media_file, media_filename, local_year, optimize_search):
	server_dup = None

	server_search_path = server_remote_base
	if optimize_search:
		server_search_path += '/' + local_year

	# ^ local_year path extension is an optimization that can cause issues if the local files were copied over in 2013 but created in 2011, for example. The original files in 2011 on the server won't be identified as duplicates because we'd only be checking the 2013 remove path

	try:
		print "check remote backup for [{}] in [{}]...".format(media_file, server_search_path)
		server_dups = subprocess.check_output(["find", server_search_path, "-name", media_filename, "-print"])
		dups = filter(bool, server_dups.split('\n'))
	except CalledProcessError:
		# print "Find exception: [{}]".format(sys.exc_info()[0])
		pass

	sha_duplicate = False
	if dups and len(dups) > 0:
		print "[{}] server dup(s) found for [{}]: [{}]".format(len(dups), media_filename, dups)

		local_sha_pipe = subprocess.Popen(['openssl', 'sha1', media_file], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
		local_sha_out, err = local_sha_pipe.communicate()
		local_sha_output_array = local_sha_out.split()
		local_sha = local_sha_output_array[len(local_sha_output_array)-1]
		print "local_sha: [{}]".format(local_sha)

		for dup in dups:
			# dup = dup[:-1] # strips off newline garbage
			# print "trimmed newline off of dup [{}], comparing shas".format(dup)

			remote_sha_pipe = subprocess.Popen(['openssl', 'sha1', dup], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
			remote_sha_out, err = remote_sha_pipe.communicate()
			remote_sha_output_array = remote_sha_out.split()
			remote_sha = remote_sha_output_array[len(remote_sha_output_array)-1]
			print "remote_sha: [{}] for [{}]".format(remote_sha, dup)
			
			if local_sha == remote_sha:
				print "[{}] sha checksum the same [{}], confirmed duplicate of remote server file [{}]. Can remove local copy [{}].".format(media_filename, local_sha, dup, media_file)
				add_file_to_cleanup(media_file)
				add_remote_file_to_test(media_file,dup)
				sha_duplicate = True
				break
			else:
				add_corrupt_pair(media_file, dup)

	return sha_duplicate

def get_creation_time(path):
	sub_output_array = subprocess.check_output(["stat", "-f%B", path])
	create_time_in_secs = filter(bool, sub_output_array.split('\n'))
	# print "get_creation_time: [{}]".format(str(datetime.datetime.fromtimestamp(float(create_time_in_secs[0]))))
	return datetime.datetime.fromtimestamp(float(create_time_in_secs[0]))

def archive_file(file):
	create_time = get_creation_time(file)
	src = file;
	dst = "archive/{:0>4d}{:0>2d}{:0>2d}_{:0>2d}{:0>2d}{:0>2d}-{}".format(create_time.year, create_time.month, create_time.day, create_time.hour, create_time.minute, create_time.second, file)
	shutil.move(src, dst)
	print "Archived {}".format(dst)

def archive_previous_run_results():
	if os.path.isfile(local_cleanup_file_name):
		archive_file(local_cleanup_file_name)
	if os.path.isfile(remote_test_file_name):
		archive_file(remote_test_file_name)
	if os.path.isfile(corrupt_pair_file_name):
		archive_file(corrupt_pair_file_name)

arg_check_dups = True
arg_remote_test = False
arg_backup_type = ".MOV"

archive_previous_run_results()

# print 'Argument List:', str(sys.argv)

try:
	opts, args = getopt.getopt(sys.argv[1:], "ht:", ["help", "type=", "skip-dup-check", "remote-test"])
except getopt.GetoptError:
	print 'backup.py [-h] -t <movies|pics|screenshots> [--skip-dup-check] [--remote-test]'
	sys.exit(2)

# print "getopt opts: [{}]".format(str(opts))
# print "getopt args: [{}]".format(str(args))

for opt, arg in opts:
	# print "Checking opt: [{}] arg: [{}]".format(opt, arg)
	if opt in ("-h", "--help"):
		print 'backup.py [-h] -t <movies|pics|screenshots> [--skip-dup-check]'
		sys.exit()
	elif opt in ("-t", "--type"):
		if arg == 'movies':
			arg_backup_type = ".MOV"
		elif arg == 'pics':
			arg_backup_type = ".JPG"
		elif arg == 'screenshots':
			arg_backup_type = ".PNG"
		print "Processing [{}] with extension: [{}]".format(arg, arg_backup_type)
	elif opt in ("--skip-dup-check"):
		print "Skipping duplicate remove file check"
		arg_check_dups = False
	elif opt in ("--remote-test"):
		print "Verifying remote file integrity only"
		arg_remote_test = True

# local_root_path = '/Users/seanmkirkpatrick/Pictures/iPhoto Library.migratedphotolibrary/Masters/2013/12/13/20131213-175159'
# local_root_path = '/Users/seanmkirkpatrick/Pictures/iPhoto Library.migratedphotolibrary/Masters/2013/12/23/20131223-181745'
# local_root_path = '/Users/seanmkirkpatrick/Pictures/iPhoto Library.migratedphotolibrary/Masters/2013/12/26/20131226-153244'
# local_root_path = '/Users/seanmkirkpatrick/Pictures/iPhoto Library.migratedphotolibrary/Masters/2013/12/12'
# local_root_path = '/Users/seanmkirkpatrick/Pictures/iPhoto Library.migratedphotolibrary/Masters/2015'
# local_root_path = '/Users/seanmkirkpatrick/Pictures/Photos Library.photoslibrary/Masters/2015'
# local_root_path = '/Users/seanmkirkpatrick/Pictures/Photos Library.photoslibrary/Masters'
local_root_path = '/Users/seanmkirkpatrick/Pictures/iPhoto Library.migratedphotolibrary/Masters/2014'

found_media1 = subprocess.check_output(["find", local_root_path, "-name", "*{}".format(arg_backup_type), "-print"])
found_media2 = subprocess.check_output(["find", local_root_path, "-name", "*{}".format(arg_backup_type.lower()), "-print"])
print "Ran check_output"

media = filter(bool, found_media1.split('\n'))
media.extend(filter(bool, found_media2.split('\n')))
media_file_info = {}
for media_file in media:
	media_file_info[media_file] = media_file.split('/')
	print "local media_file file path: [{}]".format(media_file)

exit

# for media_file in media:
# 	print "[{}] => [{}]".format(media_file, media_file_info[media_file])
# 	print "[{}] => [{}][{}]".format(media_file, media_file_info[media_file][1], media_file_info[media_file][len(media_file_info[media_file])-1])

server_remote_base = '/Volumes/pictures/MASTER PICTURES'
for media_file in media:
	print "Processing [{}]".format(media_file)

	media_file_create_time = get_creation_time(media_file)
	year = media_file_create_time.year
	media_filename = media_file_info[media_file][len(media_file_info[media_file])-1]
	print "[{}] file [{}] created: [{}/{}/{}]".format(media_file, media_filename, media_file_create_time.month, media_file_create_time.day, year)

	sys.stdout.flush()

	if arg_check_dups and check_for_remote_duplicates(media_file, media_filename, str(year), year >= 2013):
		# We're done with this file, move on
		continue

	if arg_remote_test:
		# We're not doing anything but checking the checksums for local vs remote copies
		continue

	remote_dir = server_remote_base + '/' + media_file_create_time.strftime("%Y/%Y%m/%Y%m%d/")
	remote_media_file = remote_dir + media_filename

	print "[{}] only found locally, backing up to server: [{}]".format(media_file, remote_media_file)
	sys.stdout.flush()

	try:
		os.makedirs(remote_dir, 0o755)
	except OSError as e:
		if e.errno == errno.EEXIST:
			pass
		else:
			raise

	shutil.copyfile(media_file, remote_media_file)

if local_cleanup_file is not None:
	local_cleanup_file.close()

if remote_test_file is not None:
	remote_test_file.close()

if corrupt_pair_file is not None:
	corrupt_pair_file.close()

print "All Done."
