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
remote_test_file = None

def add_file_to_cleanup(file):
	global local_cleanup_file
	if local_cleanup_file is None:
		local_cleanup_file = open('local_cleanup.sh','wx')
		local_cleanup_file.write('#!/bin/sh\n')
	local_cleanup_file.write("rm \"{}\";\n".format(file))

def add_remote_file_to_test(file):
	global remote_test_file
	if remote_test_file is None:
		remote_test_file = open('remote_test.sh','wx')
		remote_test_file.write('#!/bin/sh\n')
	remote_test_file.write("echo \"{}\";\nopen \"{}\";\nsleep 10;\n".format(file,file))

def check_for_remote_duplicates(movie, movie_file, local_year, optimize_search):
	server_dup = None

	server_search_path = server_remote_base
	if optimize_search:
		server_search_path += '/' + local_year

	# ^ local_year path extension is an optimization that can cause issues if the local files were copied over in 2013 but created in 2011, for example. The original files in 2011 on the server won't be identified as duplicates because we'd only be checking the 2013 remove path

	try:
		print "check remote backup for [{}] in [{}]...".format(movie, server_search_path)
		server_dups = subprocess.check_output(["find", server_search_path, "-name", movie_file, "-print"])
		dups = filter(bool, server_dups.split('\n'))
	except CalledProcessError:
		# print "Find exception: [{}]".format(sys.exc_info()[0])
		pass

	sha_duplicate = False
	if dups and len(dups) > 0:
		print "[{}] server dup(s) found for [{}]: [{}]".format(len(dups), movie_file, dups)

		local_sha_pipe = subprocess.Popen(['openssl', 'sha1', movie], stderr=subprocess.PIPE, stdout=subprocess.PIPE)
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
				print "[{}] sha checksum the same [{}], confirmed duplicate of remote server file [{}]. Can remove local copy [{}].".format(movie_file, local_sha, dup, movie)
				add_file_to_cleanup(movie)
				add_remote_file_to_test(dup)
				sha_duplicate = True
				break

	return sha_duplicate

def get_creation_time(path):
	sub_output_array = subprocess.check_output(["stat", "-f%B", path])
	create_time_in_secs = filter(bool, sub_output_array.split('\n'))
	# print "get_creation_time: [{}]".format(str(create_time_in_secs))
	return datetime.datetime.fromtimestamp(float(create_time_in_secs[0]))

arg_check_dups = True
arg_backup_type = ".MOV"

print 'Argument List:', str(sys.argv)

try:
	opts, args = getopt.getopt(sys.argv[1:], "ht:", ["help", "type=", "skip-dup-check"])
except getopt.GetoptError:
	print 'backup_movs.py [-h] -t <movies|pics|screenshots> [--skip-dup-check]'
	sys.exit(2)

print "getopt opts: [{}]".format(str(opts))
print "getopt args: [{}]".format(str(args))

for opt, arg in opts:
	print "Checking opt: [{}] arg: [{}]".format(opt, arg)
	if opt in ("-h", "--help"):
		print 'backup_movs.py [-h] -t <movies|pics|screenshots> [--skip-dup-check]'
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

local_root_path = '/Users/seanmkirkpatrick/Pictures/iPhoto Library.photolibrary/Masters'
found_movies = subprocess.check_output(["find", local_root_path, "-name", "*{}".format(arg_backup_type), "-print"])
print "Ran check_output"

movies = filter(bool, found_movies.split('\n'))
movie_info = {}
for movie in movies:
	movie_info[movie] = movie.split('/')
	print "local movie file path: [{}]".format(movie)

# for movie in movies:
# 	print "[{}] => [{}]".format(movie, movie_info[movie])
# 	print "[{}] => [{}][{}]".format(movie, movie_info[movie][1], movie_info[movie][len(movie_info[movie])-1])

server_remote_base = '/Volumes/pictures/MASTER PICTURES'
for movie in movies:
	print "Processing [{}]".format(movie)

	movie_create_time = get_creation_time(movie)
	year = movie_create_time.year
	movie_file = movie_info[movie][len(movie_info[movie])-1]
	print "[{}] file [{}] year: [{}]".format(movie, movie_file, year)

	sys.stdout.flush()

	if arg_check_dups and check_for_remote_duplicates(movie, movie_file, str(year), year >= 2013):
		# We're done with this file, move on
		continue

	remote_dir = server_remote_base + '/' + movie_create_time.strftime("%Y/%Y%m/%Y%m%d/")
	remote_movie = remote_dir + movie_file

	print "[{}] only found locally, backing up to server: [{}]".format(movie, remote_movie)
	sys.stdout.flush()

	continue

	try:
		os.makedirs(remote_dir, 0o755)
	except OSError as e:
		if e.errno == errno.EEXIST:
			pass
		else:
			raise

	shutil.copyfile(movie, remote_movie)

if local_cleanup_file is not None:
	local_cleanup_file.close()

if remote_test_file is not None:
	remote_test_file.close()

print "All Done."
