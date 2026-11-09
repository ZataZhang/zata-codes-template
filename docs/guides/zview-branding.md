# zview 品牌标识

`scripts/shared/view/assets/zview-mark.svg` 是查看器顶部的品牌图形，也是浏览器标签图标。更新这一个
SVG 即可同时替换两处标识；图形采用 48 × 48 的画布，包含渐变底色和白色 `Z` 字形。

派生项目可以直接替换此文件，保留文件名与正方形画布即可。查看器只通过
`scripts/shared/view/server.py` 中的静态资源白名单提供固定资源；新增或重命名标识文件时，需同步更新
白名单以及 `assets/index.html` 中的图片与 favicon 引用。
