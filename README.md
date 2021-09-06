# BeltPrinterSlicing(Beta)
このプラグインは[BLACKBELT Cura](https://github.com/BlackBelt3D/Cura)を参考に最新バージョンのCuraのプラグインとして起動するようにしたものです. 

[合同会社BirthT](https://birtht.xyz/#/)で開発しているベルトコンベア型3Dプリンタの[Leee](https://birtht.xyz/#/Leee)で実機実験をしています.

機能の要望やバグ報告は[Twitter](https://twitter.com/BirthT_3D)かissueにお願いします.

## Installation (最新バージョン)
1. [BeltPrinterSlicing.zip](https://github.com/BirthT/BeltPrinterSlicing/releases/download/v0.9.3/BeltPrinterSlicing.zip)をダウンロード
2. BeltPrinterSlicing.zipを解答
3. (Windows)解凍したフォルダ(直下に`__init__.py`がある)を`[Cura installation folder]/plugins/`にコピーする
3. (Mac)解凍したフォルダ(直下に`__init__.py`がある)を`~/Library/Application Support/cura/[YOUR CURA VERSION]/plugins/`にコピーする

## Installation (Old Version)
### Windows
1. [BeltPrinterSlicing_win.zip](https://github.com/BirthT/BeltPrinterSlicing/releases/download/0.9.0/BeltPrinterSlicing_win.zip)をダウンロード
2. BeltPrinterSlicing_win.zipを解凍
3. 解凍したフォルダ(直下に`__init__.py`がある)を`[Cura installation folder]/plugins/`にコピーする

### Mac
1. [BeltPrinterSlicing_mac.zip](https://github.com/BirthT/BeltPrinterSlicing/releases/download/0.9.0/BeltPrinterSlicing_mac.zip)をダウンロード
2. BeltPrinterSlicing_mac.zipを解凍
3. 解凍したフォルダ(直下に`__init__.py`がある)を`~/Library/Application Support/cura/[YOUR CURA VERSION]/plugins/`にコピーする


---
# BeltPrinterSlicing(Beta) - English

This is a port of the [BLACKBELT Cura](https://github.com/BlackBelt3D/Cura) plugin to work with the latest versions of Cura (4.9.1). 

It makes it possible for Cura to slice at different angles, by default the slicing angle is 35° which is tuned for the [Leee Printer](https://birtht.xyz/#/Leee) by [合同会社BirthT](https://birtht.xyz/#/)

To use it with a Creality3D 3DPrintMill CR-30; change `Extensions -> Belt Extension -> Settings -> Gantry angle` to **45°**.

Tweet @ [BirthT_3D](https://twitter.com/BirthT_3D) if you encounter any issues.

## Installation
### Windows
1. Download `BeltPrinterSlicing_win.zip` from [releases](https://github.com/BirthT/BeltPrinterSlicing/releases)
2. Unzip BeltPrinterSlicing_win.zip this will create a folder called `BeltPrinterSlicing_win`
3. Move `BeltPrinterSlicing_win` to [Cura installation folder]/plugins/BeltPrinterSlicing_win
4. Verify that [Cura installation folder]/plugins/BeltPrinterSlicing_win/__init__.py exists (i.e. you don't have a nested folder instead)

### Mac
1. Download `BeltPrinterSlicing_mac.zip` from [releases](https://github.com/BirthT/BeltPrinterSlicing/releases)
2. Unzip `BeltPrinterSlicing_mac.zip` this will create a folder called `BeltPrinterSlicing_mac`
3. Move `BeltPrinterSlicing_mac` to ~/Library/Application Support/cura/[YOUR CURA VERSION]/plugins/BeltPrinterSlicing_mac
4. Verify that ~/Library/Application Support/cura/[YOUR CURA VERSION]/plugins/BeltPrinterSlicing_mac/__init__.py exists (i.e. you don't have a nested folder instead)
