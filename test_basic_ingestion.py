#!/usr/bin/env python3
"""
Basic data ingestion test without full TFX dependencies.
This script tests if we can read and process the Chicago Taxi CSV data.
"""

import pandas as pd
import tensorflow as tf
import os
from pathlib import Path

def test_basic_data_ingestion():
    """Test basic data reading and processing"""
    
    # Define data path
    project_root = Path(__file__).parent
    data_path = project_root / "tfx_pipeline" / "data" / "simple" / "data.csv"
    
    print(f"🔍 Looking for data at: {data_path}")
    
    if not data_path.exists():
        print(f"❌ Data file not found at {data_path}")
        return False
    
    try:
        # Read CSV data
        print("📊 Reading CSV data...")
        df = pd.read_csv(data_path)
        
        print(f"✅ Successfully loaded {len(df)} rows")
        print(f"📋 Columns: {list(df.columns)}")
        print(f"🔢 Data shape: {df.shape}")
        
        # Show first few rows
        print("\n📝 First 5 rows:")
        print(df.head())
        
        # Basic data validation
        print(f"\n🔍 Missing values per column:")
        print(df.isnull().sum())
        
        # Convert to TensorFlow dataset (basic approach)
        print("\n🔄 Converting to TensorFlow dataset...")
        
        # Select numeric columns for simple test
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
        print(f"📊 Numeric columns: {list(numeric_cols)}")
        
        if len(numeric_cols) > 0:
            # Create a simple TF dataset
            dataset = tf.data.Dataset.from_tensor_slices(
                df[numeric_cols].values.astype('float32')
            )
            
            # Take a few samples
            print("\n🎯 TensorFlow dataset samples:")
            for i, sample in enumerate(dataset.take(3)):
                print(f"Sample {i+1}: shape={sample.shape}")
            
            print("✅ Basic TensorFlow dataset creation successful!")
            return True
        else:
            print("⚠️  No numeric columns found for TF dataset creation")
            return False
            
    except Exception as e:
        print(f"❌ Error during data ingestion: {str(e)}")
        return False

def test_tensorflow_installation():
    """Test TensorFlow installation"""
    try:
        print(f"🔧 TensorFlow version: {tf.__version__}")
        print(f"🖥️  GPU available: {tf.config.list_physical_devices('GPU')}")
        print(f"💾 CPU available: {tf.config.list_physical_devices('CPU')}")
        
        # Simple tensor operation test
        a = tf.constant([1, 2, 3])
        b = tf.constant([4, 5, 6])
        c = tf.add(a, b)
        print(f"🧮 Simple tensor operation: {a.numpy()} + {b.numpy()} = {c.numpy()}")
        
        return True
    except Exception as e:
        print(f"❌ TensorFlow test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🚀 Starting basic data ingestion test...")
    print("=" * 50)
    
    # Test TensorFlow
    print("\n1️⃣ Testing TensorFlow installation...")
    tf_ok = test_tensorflow_installation()
    
    # Test data ingestion
    print("\n2️⃣ Testing data ingestion...")
    data_ok = test_basic_data_ingestion()
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"   TensorFlow: {'✅ PASS' if tf_ok else '❌ FAIL'}")
    print(f"   Data Ingestion: {'✅ PASS' if data_ok else '❌ FAIL'}")
    
    if tf_ok and data_ok:
        print("\n🎉 Basic ingestion test completed successfully!")
        print("💡 Ready to proceed with more advanced TFX components")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
