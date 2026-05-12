#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据质量修复脚本
用途：在导入到 Neo4j 前检查和修复数据中的缺失字段和异常值
"""

import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Any

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataFixer:
    """数据修复工具类"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.stats = {}
    
    def fix_diseases(self, input_file: Path, output_file: Path) -> int:
        """
        修复疾病数据：补全缺失字段
        
        Args:
            input_file: 原始 diseases.json 路径
            output_file: 修复后的输出路径
        
        Returns:
            修复的记录数
        """
        logger.info(f"开始修复疾病数据：{input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                diseases = json.load(f)
        except Exception as e:
            logger.error(f"读取疾病文件失败：{e}")
            return 0
        
        fixed_count = 0
        default_values = {
            "intro": "暂无介绍",
            "treat_detail": "请咨询医生",
            "nursing": "请咨询医生",
            "cause": "暂无信息",
            "prevent": "暂无预防建议",
            "icd_code": "UNKNOWN",
        }
        
        for disease in diseases:
            # 检查必需字段
            if not disease.get("name"):
                logger.warning(f"发现缺少 name 字段的疾病：{disease}")
                continue
            
            # 补全缺失字段
            for field, default_value in default_values.items():
                if not disease.get(field):
                    disease[field] = default_value
                    fixed_count += 1
            
            # 清理症状列表（移除空值）
            if "symptom" in disease and isinstance(disease["symptom"], list):
                disease["symptom"] = [s for s in disease["symptom"] if s and str(s).strip()]
            
            # 清理药物列表
            if "drug" in disease and isinstance(disease["drug"], list):
                disease["drug"] = [d for d in disease["drug"] if d and str(d).strip()]
            
            # 清理并发症列表
            if "neopathy" in disease and isinstance(disease["neopathy"], list):
                disease["neopathy"] = [n for n in disease["neopathy"] if n and str(n).strip()]
        
        # 写入修复后的数据
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(diseases, f, ensure_ascii=False, indent=2)
            logger.info(f"疾病数据修复完成，共修复 {fixed_count} 处缺失字段")
            logger.info(f"修复后的数据已保存至：{output_file}")
            return len(diseases)
        except Exception as e:
            logger.error(f"保存修复数据失败：{e}")
            return 0
    
    def fix_insurance(self, input_file: Path, output_file: Path) -> int:
        """
        修复保险数据：补全缺失字段
        
        Args:
            input_file: 原始 insurance_info.json 路径
            output_file: 修复后的输出路径
        
        Returns:
            修复的记录数
        """
        logger.info(f"开始修复保险数据：{input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                insurances = json.load(f)
        except Exception as e:
            logger.error(f"读取保险文件失败：{e}")
            return 0
        
        fixed_count = 0
        default_values = {
            "产品名称": "未命名产品",
            "险种分类": "其他",
            "承保公司": "未知",
            "承保年龄": "无限制",
            "保障期限": "1年",
            "价格": "未标注",
            "产品描述": "暂无描述",
        }
        
        for insurance in insurances:
            # 补全缺失字段
            for field, default_value in default_values.items():
                if not insurance.get(field):
                    insurance[field] = default_value
                    fixed_count += 1
            
            # 确保有唯一标识
            if not insurance.get("产品名称") or insurance["产品名称"] == "未命名产品":
                insurance["产品名称"] = f"保险产品_{len(insurances)}"
        
        # 去重
        unique_insurances = {ins.get("产品名称"): ins for ins in insurances}
        insurances = list(unique_insurances.values())
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(insurances, f, ensure_ascii=False, indent=2)
            logger.info(f"保险数据修复完成，共修复 {fixed_count} 处缺失字段，去重后 {len(insurances)} 条")
            logger.info(f"修复后的数据已保存至：{output_file}")
            return len(insurances)
        except Exception as e:
            logger.error(f"保存修复数据失败：{e}")
            return 0
    
    def fix_nursing_homes(self, input_file: Path, output_file: Path) -> int:
        """
        修复养老院数据：提取城市、补全字段
        
        Args:
            input_file: 原始 nursing_homes.csv 路径
            output_file: 修复后的 CSV 路径
        
        Returns:
            修复的记录数
        """
        logger.info(f"开始修复养老院数据：{input_file}")
        
        # 常见城市列表，用于从地址提取城市
        CITIES = [
            "北京", "上海", "广州", "深圳", "杭州", "南京", "苏州", "武汉", "成都",
            "西安", "重庆", "天津", "长沙", "沈阳", "青岛", "大连", "宁波", "厦门"
        ]
        
        try:
            records = []
            with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 提取城市
                    address = row.get("地址", "")
                    city = "其他"
                    for c in CITIES:
                        if c in address:
                            city = c
                            break
                    
                    # 补全数据
                    record = {
                        "名称": row.get("名称", "未命名").strip(),
                        "城市": city,
                        "地址": address,
                        "性质": row.get("性质", "未知"),
                        "床位": row.get("床位", "0"),
                        "价格(元/月)": row.get("价格(元/月)", "0"),
                        "特色服务": row.get("特色服务", "暂无"),
                    }
                    
                    # 验证名称不为空
                    if record["名称"] and record["名称"] != "未命名":
                        records.append(record)
            
            # 保存修复后的数据
            if records:
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    fieldnames = ["名称", "城市", "地址", "性质", "床位", "价格(元/月)", "特色服务"]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(records)
                
                logger.info(f"养老院数据修复完成，共 {len(records)} 条记录")
                logger.info(f"修复后的数据已保存至：{output_file}")
                return len(records)
            else:
                logger.warning("养老院数据为空")
                return 0
        
        except Exception as e:
            logger.error(f"修复养老院数据失败：{e}")
            return 0
    
    def fix_all(self) -> Dict[str, int]:
        """
        执行全部数据修复
        
        Returns:
            修复结果统计
        """
        results = {}
        
        # 修复疾病数据
        diseases_input = self.data_dir / "Diseases" / "diseases.json"
        diseases_output = self.data_dir / "Diseases" / "diseases_fixed.json"
        if diseases_input.exists():
            results["diseases"] = self.fix_diseases(diseases_input, diseases_output)
        
        # 修复保险数据
        insurance_input = self.data_dir / "Insurance" / "insurance_info.json"
        insurance_output = self.data_dir / "Insurance" / "insurance_info_fixed.json"
        if insurance_input.exists():
            results["insurance"] = self.fix_insurance(insurance_input, insurance_output)
        
        # 修复养老院数据
        nursing_homes_input = self.data_dir / "NursingHomes" / "nursing_homes.csv"
        nursing_homes_output = self.data_dir / "NursingHomes" / "nursing_homes_fixed.csv"
        if nursing_homes_input.exists():
            results["nursing_homes"] = self.fix_nursing_homes(nursing_homes_input, nursing_homes_output)
        
        return results


def main():
    """主程序"""
    import sys
    
    # 确定数据目录
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    else:
        # 默认查找项目的 DataCleaned 目录
        project_root = Path(__file__).parent.parent.parent
        data_dir = project_root / "DataCleaned"
    
    if not data_dir.exists():
        logger.error(f"数据目录不存在：{data_dir}")
        sys.exit(1)
    
    # 执行修复
    fixer = DataFixer(data_dir)
    results = fixer.fix_all()
    
    # 输出统计
    logger.info("=" * 60)
    logger.info("数据修复完成统计：")
    logger.info("=" * 60)
    for key, count in results.items():
        logger.info(f"  {key}: {count} 条记录")
    logger.info("=" * 60)
    
    # 输出下一步提示
    logger.info("\n下一步：")
    logger.info("1. 检查修复后的数据文件（*_fixed 后缀）")
    logger.info("2. 如无问题，可将 *_fixed 文件覆盖原文件，或修改 neo4j_loader.py 中的文件路径")
    logger.info("3. 执行 python src/neo4j_loader.py 进行数据导入")
    logger.info("\n如有问题，请查看上方日志信息")


if __name__ == "__main__":
    main()
