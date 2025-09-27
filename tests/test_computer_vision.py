"""Tests for computer vision backbone."""

import pytest
import numpy as np
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add the project root to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sensors.computer_vision import (
    VisionBackbone, CameraType, CameraConfig, Detection, LaneInfo
)


class TestCameraType:
    """Test CameraType enum."""
    
    def test_camera_type_values(self):
        """Test that all expected camera types are present."""
        expected_types = [
            "front_wide", "front_narrow", "front_main", "rear",
            "left_repeater", "right_repeater", "left_pillar", "right_pillar"
        ]
        
        for expected_type in expected_types:
            assert hasattr(CameraType, expected_type.upper()), f"Missing camera type: {expected_type}"
    
    def test_camera_type_enum_values(self):
        """Test that enum values match expected strings."""
        assert CameraType.FRONT_WIDE.value == "front_wide"
        assert CameraType.FRONT_NARROW.value == "front_narrow"
        assert CameraType.FRONT_MAIN.value == "front_main"
        assert CameraType.REAR.value == "rear"
        assert CameraType.LEFT_REPEATER.value == "left_repeater"
        assert CameraType.RIGHT_REPEATER.value == "right_repeater"
        assert CameraType.LEFT_PILLAR.value == "left_pillar"
        assert CameraType.RIGHT_PILLAR.value == "right_pillar"


class TestCameraConfig:
    """Test CameraConfig dataclass."""
    
    def test_camera_config_creation(self):
        """Test creating a camera configuration."""
        config = CameraConfig(
            camera_type=CameraType.FRONT_MAIN,
            resolution=(1280, 960),
            fov=70.0,
            position=(0.0, 0.0, 1.5),
            rotation=(0.0, 0.0, 0.0),
            fps=30
        )
        
        assert config.camera_type == CameraType.FRONT_MAIN
        assert config.resolution == (1280, 960)
        assert config.fov == 70.0
        assert config.position == (0.0, 0.0, 1.5)
        assert config.rotation == (0.0, 0.0, 0.0)
        assert config.fps == 30
    
    def test_camera_config_default_fps(self):
        """Test that fps defaults to 30."""
        config = CameraConfig(
            camera_type=CameraType.FRONT_MAIN,
            resolution=(1280, 960),
            fov=70.0,
            position=(0.0, 0.0, 1.5),
            rotation=(0.0, 0.0, 0.0)
        )
        
        assert config.fps == 30


class TestDetection:
    """Test Detection dataclass."""
    
    def test_detection_creation(self):
        """Test creating a detection object."""
        detection = Detection(
            class_id=0,
            class_name="car",
            confidence=0.95,
            bbox=(100, 100, 200, 200),
            depth=5.0,
            velocity=(10.0, 0.0)
        )
        
        assert detection.class_id == 0
        assert detection.class_name == "car"
        assert detection.confidence == 0.95
        assert detection.bbox == (100, 100, 200, 200)
        assert detection.depth == 5.0
        assert detection.velocity == (10.0, 0.0)
    
    def test_detection_optional_fields(self):
        """Test detection with optional fields as None."""
        detection = Detection(
            class_id=1,
            class_name="person",
            confidence=0.85,
            bbox=(50, 50, 150, 150)
        )
        
        assert detection.depth is None
        assert detection.velocity is None


class TestLaneInfo:
    """Test LaneInfo dataclass."""
    
    def test_lane_info_creation(self):
        """Test creating a lane info object."""
        lane = LaneInfo(
            lane_type="solid",
            confidence=0.9,
            points=[(100, 200), (200, 200), (300, 200)],
            curvature=0.01,
            distance_to_lane=0.5
        )
        
        assert lane.lane_type == "solid"
        assert lane.confidence == 0.9
        assert len(lane.points) == 3
        assert lane.curvature == 0.01
        assert lane.distance_to_lane == 0.5


class TestVisionBackbone:
    """Test VisionBackbone class."""
    
    @pytest.fixture
    def vision_backbone(self):
        """Create a VisionBackbone instance for testing."""
        config = {
            'model_path': '/models/',
            'gpu_enabled': True,
            'batch_size': 1
        }
        return VisionBackbone(config)
    
    def test_vision_backbone_initialization(self, vision_backbone):
        """Test VisionBackbone initialization."""
        assert vision_backbone.config is not None
        assert not vision_backbone.is_initialized
        assert len(vision_backbone.cameras) == 8
        assert len(vision_backbone.models) == 0
    
    def test_camera_setup(self, vision_backbone):
        """Test that all 8 cameras are properly configured."""
        expected_cameras = [
            CameraType.FRONT_WIDE, CameraType.FRONT_NARROW, CameraType.FRONT_MAIN,
            CameraType.REAR, CameraType.LEFT_REPEATER, CameraType.RIGHT_REPEATER,
            CameraType.LEFT_PILLAR, CameraType.RIGHT_PILLAR
        ]
        
        for camera_type in expected_cameras:
            assert camera_type in vision_backbone.cameras
            camera = vision_backbone.cameras[camera_type]
            assert isinstance(camera, CameraConfig)
            assert camera.camera_type == camera_type
    
    def test_camera_configurations(self, vision_backbone):
        """Test specific camera configurations."""
        # Test front wide camera
        front_wide = vision_backbone.cameras[CameraType.FRONT_WIDE]
        assert front_wide.fov == 120.0
        assert front_wide.resolution == (1280, 960)
        
        # Test rear camera
        rear = vision_backbone.cameras[CameraType.REAR]
        assert rear.rotation == (0.0, 0.0, 180.0)
        assert rear.position[2] == -1.5  # z position should be negative for rear
        
        # Test side cameras
        left_repeater = vision_backbone.cameras[CameraType.LEFT_REPEATER]
        assert left_repeater.rotation == (0.0, 0.0, -90.0)
        assert left_repeater.position[0] == -1.0  # x position should be negative for left
    
    def test_initialize_models(self, vision_backbone):
        """Test model initialization."""
        vision_backbone.initialize_models()
        
        assert vision_backbone.is_initialized
        assert len(vision_backbone.models) == 6
        
        expected_models = [
            'object_detection', 'semantic_segmentation', 'depth_estimation',
            'lane_detection', 'traffic_light_detection', 'occupancy_network'
        ]
        
        for model_name in expected_models:
            assert model_name in vision_backbone.models
    
    def test_process_frame_structure(self, vision_backbone):
        """Test that process_frame returns expected structure."""
        # Create a dummy frame
        frame = np.random.randint(0, 255, (960, 1280, 3), dtype=np.uint8)
        
        results = vision_backbone.process_frame(CameraType.FRONT_MAIN, frame)
        
        # Check that all expected keys are present
        expected_keys = [
            'camera_type', 'detections', 'lanes', 'depth_map',
            'semantic_segmentation', 'traffic_lights', 'occupancy_grid'
        ]
        
        for key in expected_keys:
            assert key in results
        
        assert results['camera_type'] == CameraType.FRONT_MAIN
        assert isinstance(results['detections'], list)
        assert isinstance(results['lanes'], list)
        assert isinstance(results['traffic_lights'], list)
    
    def test_process_frame_initializes_models(self, vision_backbone):
        """Test that process_frame initializes models if not already done."""
        assert not vision_backbone.is_initialized
        
        frame = np.random.randint(0, 255, (960, 1280, 3), dtype=np.uint8)
        vision_backbone.process_frame(CameraType.FRONT_MAIN, frame)
        
        assert vision_backbone.is_initialized
    
    def test_fuse_multi_camera_structure(self, vision_backbone):
        """Test that fuse_multi_camera returns expected structure."""
        # Create dummy camera results
        camera_results = {}
        for camera_type in CameraType:
            camera_results[camera_type] = {
                'detections': [],
                'lanes': [],
                'depth_map': None,
                'semantic_segmentation': None,
                'traffic_lights': [],
                'occupancy_grid': None
            }
        
        fused_results = vision_backbone.fuse_multi_camera(camera_results)
        
        expected_keys = [
            'unified_detections', 'unified_lanes', 'bird_eye_view',
            'occupancy_map', 'trajectory_prediction'
        ]
        
        for key in expected_keys:
            assert key in fused_results
    
    def test_get_camera_calibration(self, vision_backbone):
        """Test camera calibration retrieval."""
        calibration = vision_backbone.get_camera_calibration(CameraType.FRONT_MAIN)
        
        expected_keys = [
            'intrinsic_matrix', 'distortion_coeffs', 'extrinsic_matrix',
            'resolution', 'fov', 'position', 'rotation'
        ]
        
        for key in expected_keys:
            assert key in calibration
        
        assert calibration['resolution'] == (1280, 960)
        assert calibration['fov'] == 70.0
        assert isinstance(calibration['intrinsic_matrix'], np.ndarray)
        assert calibration['intrinsic_matrix'].shape == (3, 3)
        assert isinstance(calibration['distortion_coeffs'], np.ndarray)
        assert len(calibration['distortion_coeffs']) == 5
    
    def test_get_camera_calibration_invalid_camera(self, vision_backbone):
        """Test that invalid camera type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown camera type"):
            vision_backbone.get_camera_calibration("invalid_camera")
    
    def test_update_camera_parameters(self, vision_backbone):
        """Test updating camera parameters."""
        original_fov = vision_backbone.cameras[CameraType.FRONT_MAIN].fov
        
        vision_backbone.update_camera_parameters(
            CameraType.FRONT_MAIN,
            fov=80.0,
            fps=60
        )
        
        camera = vision_backbone.cameras[CameraType.FRONT_MAIN]
        assert camera.fov == 80.0
        assert camera.fps == 60
        assert camera.fov != original_fov
    
    def test_update_camera_parameters_invalid_camera(self, vision_backbone):
        """Test that updating invalid camera type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown camera type"):
            vision_backbone.update_camera_parameters("invalid_camera", fov=80.0)
    
    def test_update_camera_parameters_invalid_param(self, vision_backbone):
        """Test that updating invalid parameter raises ValueError."""
        with pytest.raises(ValueError, match="Unknown camera parameter"):
            vision_backbone.update_camera_parameters(
                CameraType.FRONT_MAIN,
                invalid_param=123
            )
    
    def test_get_system_status(self, vision_backbone):
        """Test system status retrieval."""
        status = vision_backbone.get_system_status()
        
        expected_keys = [
            'is_initialized', 'active_cameras', 'model_status',
            'processing_fps', 'memory_usage', 'gpu_utilization'
        ]
        
        for key in expected_keys:
            assert key in status
        
        assert status['active_cameras'] == 8
        assert not status['is_initialized']
        assert isinstance(status['model_status'], dict)
        # Model status should be empty before initialization
        assert len(status['model_status']) == 0
    
    def test_get_system_status_after_initialization(self, vision_backbone):
        """Test system status after model initialization."""
        vision_backbone.initialize_models()
        status = vision_backbone.get_system_status()
        
        assert status['is_initialized']
        
        # All models should be None (not loaded) in this test
        for model_name, model_loaded in status['model_status'].items():
            assert not model_loaded  # All models are None in our implementation


class TestVisionBackboneIntegration:
    """Integration tests for VisionBackbone."""
    
    @pytest.fixture
    def vision_backbone(self):
        """Create a VisionBackbone instance for integration testing."""
        config = {
            'model_path': '/models/',
            'gpu_enabled': True,
            'batch_size': 1
        }
        return VisionBackbone(config)
    
    def test_full_pipeline_simulation(self, vision_backbone):
        """Test the full vision pipeline with multiple cameras."""
        # Create dummy frames for all cameras
        frames = {}
        for camera_type in CameraType:
            frames[camera_type] = np.random.randint(0, 255, (960, 1280, 3), dtype=np.uint8)
        
        # Process all frames
        camera_results = {}
        for camera_type, frame in frames.items():
            results = vision_backbone.process_frame(camera_type, frame)
            camera_results[camera_type] = results
        
        # Verify all cameras were processed
        assert len(camera_results) == 8
        
        # Test multi-camera fusion
        fused_results = vision_backbone.fuse_multi_camera(camera_results)
        
        # Verify fusion results structure
        assert 'unified_detections' in fused_results
        assert 'unified_lanes' in fused_results
        assert 'bird_eye_view' in fused_results
        assert 'occupancy_map' in fused_results
        assert 'trajectory_prediction' in fused_results
    
    def test_camera_parameter_modification(self, vision_backbone):
        """Test modifying camera parameters and verifying changes."""
        # Get original calibration
        original_calibration = vision_backbone.get_camera_calibration(CameraType.FRONT_MAIN)
        original_fov = original_calibration['fov']
        
        # Update camera parameters
        vision_backbone.update_camera_parameters(
            CameraType.FRONT_MAIN,
            fov=90.0,
            fps=60
        )
        
        # Get updated calibration
        updated_calibration = vision_backbone.get_camera_calibration(CameraType.FRONT_MAIN)
        
        # Verify changes
        assert updated_calibration['fov'] == 90.0
        assert updated_calibration['fov'] != original_fov
        
        # Verify camera config was updated
        camera = vision_backbone.cameras[CameraType.FRONT_MAIN]
        assert camera.fov == 90.0
        assert camera.fps == 60
