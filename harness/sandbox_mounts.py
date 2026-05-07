from agents.sandbox.entries import DockerVolumeMountStrategy, S3Mount

from harness.filesystem import S3FilesystemConfig


def build_s3_mount(fs: S3FilesystemConfig) -> S3Mount:
    return S3Mount(
        bucket=fs.bucket,
        prefix=fs.prefix or None,
        mount_strategy=DockerVolumeMountStrategy(driver="rclone"),
    )
