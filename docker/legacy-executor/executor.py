#!/usr/bin/env python3
"""
Legacy Binary Executor for Rosetta Zero.

Executes legacy binaries in isolated container environment with comprehensive
side effect capture (file system writes, network operations, stdout, stderr).
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import hashlib

# AWS SDK
import boto3
from aws_lambda_powertools import Logger

logger = Logger(service="legacy-executor")

class SideEffectCapture:
    """Captures side effects during legacy binary execution."""
    
    def __init__(self):
        self.file_writes: List[Dict[str, Any]] = []
        self.network_operations: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def start_capture(self):
        """Start capturing side effects."""
        self.start_time = time.time()
        
        # Start file system monitoring
        self._start_fs_monitor()
        
        # Start network monitoring
        self._start_network_monitor()
    
    def stop_capture(self):
        """Stop capturing side effects."""
        self.end_time = time.time()
        
        # Stop monitors
        self._stop_fs_monitor()
        self._stop_network_monitor()
        
        # Collect captured data
        self._collect_fs_writes()
        self._collect_network_ops()
    
    def _start_fs_monitor(self):
        """Start file system monitoring using inotifywait."""
        # Monitor /app/output directory for file writes
        cmd = [
            "inotifywait",
            "-m",  # Monitor continuously
            "-r",  # Recursive
            "-e", "create,modify,delete",  # Events to monitor
            "--format", "%T|%e|%w%f",  # Output format
            "--timefmt", "%s",  # Timestamp format
            "/app/output"
        ]
        
        self.fs_monitor_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info("Started file system monitoring")
    
    def _stop_fs_monitor(self):
        """Stop file system monitoring."""
        if hasattr(self, 'fs_monitor_proc'):
            self.fs_monitor_proc.terminate()
            self.fs_monitor_proc.wait(timeout=5)
            logger.info("Stopped file system monitoring")
    
    def _start_network_monitor(self):
        """Start network monitoring using tcpdump."""
        cmd = [
            "tcpdump",
            "-i", "any",  # All interfaces
            "-w", "/app/side-effects/network.pcap",  # Output file
            "-U"  # Unbuffered
        ]
        
        self.network_monitor_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        logger.info("Started network monitoring")
    
    def _stop_network_monitor(self):
        """Stop network monitoring."""
        if hasattr(self, 'network_monitor_proc'):
            self.network_monitor_proc.terminate()
            self.network_monitor_proc.wait(timeout=5)
            logger.info("Stopped network monitoring")
    
    def _collect_fs_writes(self):
        """Collect file system write operations."""
        if hasattr(self, 'fs_monitor_proc'):
            output, _ = self.fs_monitor_proc.communicate(timeout=1)
            
            for line in output.splitlines():
                if line.strip():
                    parts = line.split('|')
                    if len(parts) == 3:
                        timestamp, event, filepath = parts
                        
                        # Read file content if it exists
                        content = None
                        content_hash = None
                        if os.path.exists(filepath) and os.path.isfile(filepath):
                            try:
                                with open(filepath, 'rb') as f:
                                    content_bytes = f.read()
                                    content_hash = hashlib.sha256(content_bytes).hexdigest()
                                    # Store content as base64 for JSON serialization
                                    import base64
                                    content = base64.b64encode(content_bytes).decode('utf-8')
                            except Exception as e:
                                logger.warning(f"Failed to read file {filepath}: {e}")
                        
                        self.file_writes.append({
                            'timestamp': int(timestamp),
                            'event': event,
                            'filepath': filepath,
                            'content_hash': content_hash,
                            'content': content
                        })
        
        logger.info(f"Collected {len(self.file_writes)} file system operations")
    
    def _collect_network_ops(self):
        """Collect network operations from pcap file."""
        pcap_file = "/app/side-effects/network.pcap"
        
        if os.path.exists(pcap_file):
            # Parse pcap file to extract network operations
            # For now, just record that network activity occurred
            file_size = os.path.getsize(pcap_file)
            
            if file_size > 24:  # PCAP header is 24 bytes
                self.network_operations.append({
                    'timestamp': int(time.time()),
                    'pcap_file': pcap_file,
                    'pcap_size_bytes': file_size,
                    'has_network_activity': True
                })
                
                logger.info(f"Detected network activity: {file_size} bytes")
        
        logger.info(f"Collected {len(self.network_operations)} network operations")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert captured side effects to dictionary."""
        return {
            'file_writes': self.file_writes,
            'network_operations': self.network_operations,
            'execution_duration_ms': int((self.end_time - self.start_time) * 1000) if self.start_time and self.end_time else 0
        }


class LegacyBinaryExecutor:
    """Executes legacy binaries with side effect capture."""
    
    def __init__(self):
        self.s3_client = boto3.client('s3')
        self.capture = SideEffectCapture()
    
    def execute(self, test_vector: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute legacy binary with test vector input.
        
        Args:
            test_vector: Test vector containing binary path and input parameters
            
        Returns:
            Execution result with outputs and side effects
        """
        logger.info(f"Executing test vector: {test_vector.get('vector_id')}")
        
        # Download legacy binary from S3
        binary_path = self._download_binary(
            test_vector['binary_s3_bucket'],
            test_vector['binary_s3_key']
        )
        
        # Make binary executable
        os.chmod(binary_path, 0o755)
        
        # Prepare input
        input_data = self._prepare_input(test_vector['input_parameters'])
        
        # Start side effect capture
        self.capture.start_capture()
        
        # Execute binary
        start_time = time.time()
        
        try:
            result = subprocess.run(
                [binary_path],
                input=input_data,
                capture_output=True,
                timeout=300,  # 5 minute timeout
                text=False  # Binary mode for exact byte capture
            )
            
            return_value = result.returncode
            stdout = result.stdout
            stderr = result.stderr
            error = None
            
        except subprocess.TimeoutExpired as e:
            return_value = -1
            stdout = e.stdout or b''
            stderr = e.stderr or b''
            error = {
                'type': 'TimeoutError',
                'message': 'Execution exceeded 5 minute timeout'
            }
            logger.error("Execution timeout")
            
        except Exception as e:
            return_value = -1
            stdout = b''
            stderr = str(e).encode('utf-8')
            error = {
                'type': type(e).__name__,
                'message': str(e)
            }
            logger.error(f"Execution failed: {e}")
        
        finally:
            end_time = time.time()
            
            # Stop side effect capture
            self.capture.stop_capture()
        
        # Build execution result
        execution_result = {
            'test_vector_id': test_vector['vector_id'],
            'implementation_type': 'LEGACY',
            'execution_timestamp': datetime.utcnow().isoformat(),
            'return_value': return_value,
            'stdout': stdout.hex(),  # Hex encoding for binary data
            'stderr': stderr.hex(),
            'side_effects': self.capture.to_dict(),
            'execution_duration_ms': int((end_time - start_time) * 1000),
            'error': error
        }
        
        logger.info(f"Execution completed: return_value={return_value}, duration={execution_result['execution_duration_ms']}ms")
        
        return execution_result
    
    def _download_binary(self, bucket: str, key: str) -> str:
        """Download legacy binary from S3."""
        local_path = f"/app/binaries/{Path(key).name}"
        
        logger.info(f"Downloading binary from s3://{bucket}/{key}")
        
        self.s3_client.download_file(bucket, key, local_path)
        
        logger.info(f"Binary downloaded to {local_path}")
        
        return local_path
    
    def _prepare_input(self, input_parameters: Dict[str, Any]) -> bytes:
        """Prepare input data for binary execution."""
        # Convert input parameters to format expected by legacy binary
        # For now, serialize as JSON and encode
        input_json = json.dumps(input_parameters)
        return input_json.encode('utf-8')


def main():
    """Main entry point for legacy binary executor."""
    logger.info("Legacy Binary Executor starting")
    
    # Read test vector from environment or stdin
    test_vector_json = os.environ.get('TEST_VECTOR')
    
    if not test_vector_json:
        # Read from stdin
        test_vector_json = sys.stdin.read()
    
    if not test_vector_json:
        logger.error("No test vector provided")
        sys.exit(1)
    
    try:
        test_vector = json.loads(test_vector_json)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid test vector JSON: {e}")
        sys.exit(1)
    
    # Execute binary
    executor = LegacyBinaryExecutor()
    result = executor.execute(test_vector)
    
    # Write result to stdout
    print(json.dumps(result))
    
    logger.info("Legacy Binary Executor completed")


if __name__ == '__main__':
    main()
