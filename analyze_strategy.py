#!/usr/bin/env python3
"""
Script to analyze the NostalgiaForInfinityX6 strategy structure
"""
import re
import json
from typing import Dict, List, Tuple

def extract_class_info():
    """Extract class definition and key attributes"""
    with open('NostalgiaForInfinityX6.py', 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    class_start = None
    for i, line in enumerate(lines):
        if 'class NostalgiaForInfinityX6' in line:
            class_start = i
            break
    
    if class_start:
        print("=== CLASS DEFINITION ===")
        for i in range(class_start, min(class_start + 50, len(lines))):
            if lines[i].strip() and not lines[i].startswith('  #'):
                print(f"{i+1:4d}: {lines[i]}")
                if 'def ' in lines[i] and i > class_start + 10:
                    break

def extract_method_signatures():
    """Extract all method signatures"""
    with open('NostalgiaForInfinityX6.py', 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    methods = []
    
    for i, line in enumerate(lines):
        if line.strip().startswith('def ') and not line.strip().startswith('def _'):
            methods.append((i+1, line.strip()))
    
    print("\n=== METHOD SIGNATURES ===")
    for line_num, method in methods:
        print(f"{line_num:4d}: {method}")

def extract_indicators_section():
    """Extract indicators calculation section"""
    with open('NostalgiaForInfinityX6.py', 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    start_idx = None
    for i, line in enumerate(lines):
        if 'def populate_indicators(' in line:
            start_idx = i
            break
    
    if start_idx:
        print("\n=== POPULATE INDICATORS SECTION (first 100 lines) ===")
        for i in range(start_idx, min(start_idx + 100, len(lines))):
            if lines[i].strip():
                print(f"{i+1:4d}: {lines[i]}")

def extract_entry_conditions():
    """Extract entry conditions"""
    with open('NostalgiaForInfinityX6.py', 'r') as f:
        content = f.read()
    
    entry_patterns = re.findall(r'long_entry_conditions\.append\((.*?)\)', content, re.DOTALL)
    
    print("\n=== ENTRY CONDITIONS ===")
    for i, condition in enumerate(entry_patterns[:10]):  # Show first 10
        print(f"Condition {i+1}: {condition.strip()}")

def extract_exit_conditions():
    """Extract exit conditions"""
    with open('NostalgiaForInfinityX6.py', 'r') as f:
        content = f.read()
    
    exit_methods = re.findall(r'def (.*exit.*)\(', content)
    
    print("\n=== EXIT METHODS ===")
    for method in exit_methods:
        print(f"- {method}")

def analyze_performance_issues():
    """Analyze potential performance issues"""
    with open('NostalgiaForInfinityX6.py', 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    issues = []
    
    for i, line in enumerate(lines):
        if 'ta.RSI(' in line or 'ta.EMA(' in line or 'ta.SMA(' in line:
            issues.append(f"Line {i+1}: Potential repeated indicator calculation")
        
        if len(line) > 200 and ('&' in line or '|' in line):
            issues.append(f"Line {i+1}: Very complex condition (length: {len(line)})")
    
    print("\n=== POTENTIAL PERFORMANCE ISSUES ===")
    for issue in issues[:20]:  # Show first 20
        print(issue)

if __name__ == "__main__":
    extract_class_info()
    extract_method_signatures()
    extract_indicators_section()
    extract_entry_conditions()
    extract_exit_conditions()
    analyze_performance_issues()
