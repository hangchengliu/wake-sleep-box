== 备份说明 ==
source-*.tar.gz:  项目源码，包含 display_name 固件、工具脚本、网页看板、文档。
flash-*/:         整片 16MB Flash 镜像，包含所有分区(bootloader、ota_0 小智、ota_1 Wake、model、nvs)。

== 恢复方法 ==
1. 恢复源码: tar -xzf source-20261023-135408.tar.gz
2. 恢复 Flash: 先跑 tools/backup_flash.sh 备份当前状态，再用 esptool write-flash 按地址写回分区切片。
   具体恢复命令需要 Claude 根据 partition_table.bin 解析后生成，不要盲目写入。
