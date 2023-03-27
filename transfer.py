#!/usr/bin/python3
import sys
import os
import warnings
import argparse
import threading

from termcolor import cprint
warnings.filterwarnings(action='ignore', module='paramiko\.*')
import paramiko
import logging
import subprocess

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
####new additions####
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import ProgressBar

#set up the logger
log_format = "%(asctime)s - %(message)s"
logging.basicConfig(format = log_format, stream=sys.stdout, level = logging.ERROR)
logger = logging.getLogger()

class TransferProgress:
    def __init__(self, total):
        self.num = 0
        self.n = total

    def __iter__(self):
        return self

    def __next__(self):
        if self.num < self.n:
            return self.num
        raise StopIteration()

    def __len__(self):
        return self.n

    def set_progress(self, progress):
        self.num = progress

def pb_func(tp):
    with ProgressBar() as pb:
        for _ in pb(tp):
            continue

#set up the class need host, port, username, password, key for connection 
#also will need transport and sftp 
class SFTPTransfer:
    def __init__(self, host, port, username, password, key):
        self.host = host
        self.username = username 
        self.password = password
        self.port = port
        self.key = key
        self.transport = None
        self.sftp = None 

    def connect(self):
        try:
            self.transport = paramiko.Transport((self.host, int(self.port)))
            #check to see if the user is passing in a password or a key for authentication 
            if self.key == None:
                self.transport.connect(hostkey=None, username=self.username, password=self.password)
            else: 
                self.transport.connect(hostkey=None, username=self.username,
                        pkey=paramiko.RSAKey(file_obj=open(self.key,'r')))
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        except paramiko.AuthenticationException as e:
            print("Authentication Failed: " + e)

    #remote download file from host 
    def remote_download(self, remote_path, local_path):
        #ensure self.sftp is set, if for some reason it is not set it now to avoid errors
        if self.sftp is None:
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        #get the file size for the remote file, should probably have a large file warning in the future 
        file_size = self.sftp.stat(remote_path).st_size
        #create trans_prog and set it = to the transfer progress to the size of the remote file 
        trans_prog = TransferProgress(file_size)
        pb_thread = threading.Thread(target=pb_func,args=(trans_prog,))
        def tx_cb(trans, total):
            nonlocal trans_prog
            trans_prog.set_progress(trans)
        pb_thread.daemon = True
        pb_thread.start()
        self.sftp.get(remote_path, local_path, callback=tx_cb)
    def remote_upload(self, remote_path, local_path):
        if self.sftp is None:
            self.sftp = paramiko.SFTPClient.from_transport(self.transport)
        self.sftp.put(local_path, remote_path)
    
    def disconnect(self):
        if self.sftp:
            self.sftp.close()
        if self.transport:
            self.transport.close()

def banner():
    cprint('''
      __             __
   .-'.'     .-.     '.'-.
 .'.((      ( ^ `>     )).'.
/`'- \'. _____\ (_____.'/ -'`\ 
|-''`.'------' '------'.`''-|
|.-'`.'.'.`/ | | \`.'.'.`'-.|
 \ .' . /  | | | |  \ . '. /
  '._. :  _|_| |_|_  : ._.'
     ````` /T"Y"T\ `````
          / | | | \    transport v1.0
         `'`'`'`'`'`   Created By: ice-wzl
    ''', 'light_cyan', attrs=['bold'])

if __name__ == '__main__':
    
    parser = argparse.ArgumentParser()

    parser.add_argument("-t", "--target", action="store", dest="target")
    parser.add_argument("-P", "--port", action="store", dest="port")
    parser.add_argument("-u", "--username", action="store", dest="username")
    group_k_or_p = parser.add_mutually_exclusive_group(required=True)
    group_k_or_p.add_argument("-k", "--key", action="store", dest="key")
    group_k_or_p.add_argument("-p", "--password", action="store", dest="password")
    
    args = parser.parse_args()
    banner()


    style = Style.from_dict({
    # User input (default text).
        '':          '#ff0066',
    # Prompt.
        'username': '#BBEEFF',
        'at':       '#00aa00',
        'colon':    '#EAF76B',
        'pound':    '#00aa00',
        'host':     '#00ffff bg:#444400',
        #'path':     'ansicyan underline',
    })
    message = [
        ('class:username', args.username),
        ('class:at',       '@'),
        ('class:host',     args.target),
        ('class:colon',    ':'),
        #('class:path',     os.getcwd()),
        ('class:pound',    '# '),
    ]

    html_completer = WordCompleter(['lcd', 'lls', 'upload', 'download', 'exit', 'pwd', 'cat', 'clear'])

#TODO 

    try:
        if not args.target or not args.username or not args.port or not args.password and not args.key:
            logging.error("Wrong number of args, require {username, target, port, password|key}")
            sys.exit(2)
        else:
            while True:
                transfer = SFTPTransfer(args.target, args.port, args.username, args.password, args.key)
                
                session = PromptSession(history=FileHistory('history.txt'))
                read_in_user_input = session.prompt(message=message, style=style, completer=html_completer)
                read_in_user_input = read_in_user_input.lower()
                read_in_user_input = read_in_user_input.rstrip()
                if read_in_user_input == "exit":
                    sys.exit(10)
                elif read_in_user_input == "upload":
                    transfer.connect()
                    local_path = input("local file to put up: ")
                    remote_path = input("remote path for file: ")
                    transfer.remote_upload(remote_path, local_path)
                    print("Upload Success " + remote_path)
                    transfer.disconnect()
                elif read_in_user_input == "download":
                    transfer.connect() 
                    remote_path = input("remote file to grab: ")
                    target_dir = os.getcwd() + "/" + transfer.host
                    if not os.path.exists(target_dir):
                        os.mkdir(target_dir)
                    local_path_dir = target_dir + "/".join(remote_path.split("/")[:-1])
                    if not os.path.exists(local_path_dir):
                        os.makedirs(local_path_dir)
                    local_path = local_path_dir + "/" + remote_path.split("/")[-1]
                    transfer.remote_download(remote_path, local_path)
                    print("Download Success " + remote_path)
                    transfer.disconnect()
                elif read_in_user_input == "pwd":
                   print(os.getcwd())
                elif read_in_user_input.split(" ")[0] == "cat":
                    os.system('cat ' + read_in_user_input.split(" ")[1])
                elif read_in_user_input.split(" ")[0] == "lls":
                    if len(read_in_user_input.split(" ")) == 1:
                        print(subprocess.check_output(['ls', '-la']).decode('utf-8'))
                    else:
                        print(subprocess.check_output(['ls', '-la', read_in_user_input.split(" ")[1]]).decode('utf-8'))
                elif read_in_user_input == "clear":
                    os.system("clear")
                elif read_in_user_input == "help":
                    print('''
                exit     --> exit program
                help     --> print this menu
                upload   --> put local file on remote machine
                download --> download remote file to location machine. 
                             save path is your pwd + remote file name 
                lcd      --> change local directory
                lls      --> list current local directory
                cat      --> view file
                pwd      --> see current working directory 
                clear    --> clear screen''')
                elif "lcd" in read_in_user_input:
                    os.chdir(read_in_user_input.split(" ")[1])
                    session.prompt(message=message, style=style)
                else:
                    print("Unknown Command, run help to see your options.")

    except Exception as e:
        print(e)
