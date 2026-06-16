# 产品标识与目录映射

下表来自仓库 `脚本提交明细说明.md` 与实际目录扫描。**草稿目录默认平铺**——`temp/<product>/` 直接放脚本，不分 `tdsql/oracle` 子目录，除非该产品的现有脚本已经分了。

## 行业应用产品（saas-database/行业应用）

| 顺序码 | 产品标识              | 中文说明              | 草稿目录                          | 归档目录                            |
|--------|-----------------------|-----------------------|-----------------------------------|-------------------------------------|
| 01     | standard              | 标准产品              | `行业应用/temp/01_standard/`        | `行业应用/business/01_standard/`     |
| 02     | voucher               | 电子凭证              | `行业应用/temp/02_voucher/`         | `行业应用/business/02_voucher/`      |
| 03     | bill_collection       | 电子档案              | `行业应用/temp/03_bill_collection/` | `行业应用/business/03_bill_collection/` |
| 04     | complex_charge        | 综合收费              | `行业应用/temp/04_complex_charge/`  | `行业应用/business/04_complex_charge/` |
| 05     | finance_payment       | 财政预交金            | `行业应用/temp/05_finance_payment/` | `行业应用/business/05_finance_payment/` |
| 06     | agg_settle            | 聚合交付              | `行业应用/temp/06_agg_settle/`      | `行业应用/business/06_agg_settle/`   |
| 07     | projectized           | 项目化                | `行业应用/temp/07_projectized/`     | `行业应用/business/07_projectized/`  |
| 08     | cloud_sign            | 云签                  | `行业应用/temp/08_cloud_sign/`      | `行业应用/business/08_cloud_sign/`   |
| 09     | emg_center            | 应急中心              | `行业应用/temp/09_emg_center/`      | `行业应用/business/09_emg_center/`   |
| 10     | hr_circulation        | 人事流转              | `行业应用/temp/10_hr_circulation/`  | `行业应用/business/10_hr_circulation/` |
| 11     | digital_bill          | 数字票据              | `行业应用/temp/11_digital_bill/`    | `行业应用/business/11_digital_bill/` |
| 12     | circulation_voucher   | 流转凭证              | `行业应用/temp/12_circulation_voucher/` | `行业应用/business/12_circulation_voucher/` |
| 13     | certificate           | 凭证                  | `行业应用/temp/13_certificate/`     | `行业应用/business/13_certificate/`  |
| 14     | reconcile             | 对账                  | `行业应用/temp/14_reconcile/`       | `行业应用/business/14_reconcile/`    |
| 15     | custom_report         | 自定义报表            | `行业应用/temp/15_custom_report/`   | `行业应用/business/15_custom_report/` |
| 17     | cre_business          | 信用业务              | `行业应用/temp/17_cre_business/`    | `行业应用/business/17_cre_business/` |
| 18     | data_gateway          | 数据网关              | `行业应用/temp/18_data_gateway/`    | `行业应用/business/18_data_gateway/` |
| 19     | accounting_biz        | 会计记账              | `行业应用/temp/19_accounting_biz/`  | `行业应用/business/19_accounting_biz/` |
| 20     | ai_agent              | AI Agent              | `行业应用/temp/20_ai_agent/`        | `行业应用/business/20_ai_agent/`     |
| 20     | reconcile_biz         | 对账业务              | `行业应用/temp/20_reconcile_biz/`   | `行业应用/business/20_reconcile_biz/` |
| 21     | income                | 收入                  | `行业应用/temp/21_income/`          | `行业应用/business/21_income/`       |
| 22     | certificate_nontax    | 非税电子凭证          | `行业应用/temp/22_certificate_nontax/` | `行业应用/business/22_certificate_nontax/` |
| 23     | openapi               | 开放 API              | `行业应用/temp/23_openapi/`         | `行业应用/business/23_openapi/`      |
| 24     | bill_prepose          | 票据前置              | `行业应用/temp/24_bill_prepose/`    | `行业应用/business/24_bill_prepose/` |

## 运营支撑（saas-database/运营支撑门户）

运营支撑产品在 `运营支撑门户/temp/<product>/` 下，结构与行业应用一致。常见的有 `auth`（权限）、`tenant`（租户）等，具体以仓库实际目录为准。

## 历史草稿（backup）

每次发布会把 `temp/<product>/` 切到 `行业应用/backup/<product>/<yyyymmdd>/`。看相邻脚本时，**优先看该产品 backup 最近一天的目录**——里面是真实生产风格的最新样本。

## 命名约束

- **产品标识用下划线拼接**，长度不超过 15 字符（Flyway 表名 `_SCHEMA_VERSION` 占 15 字符，组合后不能超 30）。
- 表名前缀通常和产品有关：
  - `rec_*` → 14_reconcile / 19_accounting_biz / 20_reconcile_biz
  - `gwb_*` → 18_data_gateway
  - `nontax_*` → 22_certificate_nontax
  - `auth_*` → 运营支撑权限
- 不确定产品归属时，搜索 `grep -r "missTable(\"<table>\"" 行业应用/` 找该表的建表脚本，所在目录就是产品。
