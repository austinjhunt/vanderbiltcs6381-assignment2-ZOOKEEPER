def main():
    pass

if __name__ == "__main__":
    main()


import subprocess

ifconfig_output = subprocess.run(['ifconfig'], stdout=subprocess.PIPE)
ip_address =  ifconfig_output.stdout.decode('utf-8').split('\n')[1].strip().split(' ')[1]   
    