import subprocess


def deploy(branch):
    print("deploying", branch)
    subprocess.run(f"git push origin {branch}", shell=True, check=True)
