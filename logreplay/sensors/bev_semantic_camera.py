# -*- coding: utf-8 -*-
"""
CARLA Semantic Camera Sensor
"""
# Author: Runsheng Xu <rxx3386@ucla.edu>
# License: TDG-Attribution-NonCommercial-NoDistrib

import weakref

import carla
import cv2
import numpy as np


class BEVSemanticCamera:
    """
    BEV camera for semantic segmentation.

    Parameters
    ----------
    vehicle : carla.Vehicle
        The carla.Vehicle, this is for cav.

    world : carla.World
        The carla world object, this is for rsu.

    config : dict
        Semantic camera configuration.

    global_position : list
        Global position of the infrastructure, [x, y, z]

    Attributes
    ----------
    image : np.ndarray
        Current received rgb image.
    sensor : carla.sensor
        The carla sensor that mounts at the vehicle.

    """

    def __init__(self, agent_id, vehicle, world, config, global_position):
        if vehicle is not None:
            world = vehicle.get_world()

        self.agent_id = agent_id
        blueprint = world.get_blueprint_library().\
            find('sensor.camera.semantic_segmentation')
        blueprint.set_attribute('fov', str(config['fov']))
        blueprint.set_attribute('image_size_x', str(config['image_size_x']))
        blueprint.set_attribute('image_size_y', str(config['image_size_y']))
        self.height = config['height']
        self.visualize = config['visualize']

        spawn_point = self.spawn_point_estimation(global_position)

        if vehicle is not None:
            self.sensor = world.spawn_actor(
                blueprint, spawn_point, attach_to=vehicle)
        else:
            self.sensor = world.spawn_actor(blueprint, spawn_point)

        self.image = None
        self.timstamp = None
        self.frame = 0
        weak_self = weakref.ref(self)
        self.sensor.listen(
            lambda event: BEVSemanticCamera._on_rgb_image_event(
                weak_self, event))

        # camera attributes
        self.image_width = int(self.sensor.attributes['image_size_x'])
        self.image_height = int(self.sensor.attributes['image_size_y'])

    def spawn_point_estimation(self, global_position):

        pitch = -90
        carla_location = carla.Location(x=0, y=0, z=self.height)

        if global_position is not None:
            carla_location = carla.Location(
                x=global_position[0],
                y=global_position[1],
                z=self.height)

        carla_rotation = carla.Rotation(roll=0, yaw=0, pitch=pitch)
        spawn_point = carla.Transform(carla_location, carla_rotation)

        return spawn_point

    @staticmethod
    def labels_to_array(bgr_image):
        """
        Convert an image containing CARLA semantic segmentation labels to a
        2D array containing the label of each pixel.

        Parameters
        ----------
        bgr_image : np.ndarray
            BGR image
        """
        return bgr_image[:, :, 2]

    @staticmethod
    def labels_to_cityscapes_palette(label):
        """
        Convert an image containing CARLA semantic segmentation labels to
        Cityscapes palette.

        Parameters
        ----------
        label : np.ndarray
           label image, (h, w)

        Returns
        -------
        Converted BGR image.
        """
        classes = {
            0: [0, 0, 0],  # None
            1: [70, 70, 70],  # Buildings
            2: [190, 153, 153],  # Fences
            3: [72, 0, 90],  # Other
            4: [220, 20, 60],  # Pedestrians
            5: [153, 153, 153],  # Poles
            6: [157, 234, 50],  # RoadLines
            7: [128, 64, 128],  # Roads
            8: [244, 35, 232],  # Sidewalks
            9: [107, 142, 35],  # Vegetation
            10: [0, 0, 255],  # Vehicles
            11: [102, 102, 156],  # Walls
            12: [220, 220, 0],  # TrafficSigns
            13: [70, 130, 180]  # Sky
        }
        result = np.zeros((label.shape[0], label.shape[1], 3), dtype=np.uint8)
        for key, value in classes.items():
            result[np.where(label == key)] = value
        return result

    @staticmethod
    def _on_rgb_image_event(weak_self, event):
        """CAMERA  method"""
        self = weak_self()
        if not self:
            return
        image = np.array(event.raw_data)
        image = image.reshape((self.image_height, self.image_width, 4))
        # we need to remove the alpha channel
        image = image[:, :, :3]
        # self.image is the dumped data
        self.image = np.array(self.labels_to_array(image), dtype=np.int)
        self.vis_image = \
            cv2.cvtColor(self.labels_to_cityscapes_palette(self.image),
                         cv2.COLOR_BGR2RGB)

        self.frame = event.frame
        self.timestamp = event.timestamp

    def visualize_data(self):
        if self.visualize:
            while not hasattr(self, 'vis_image') or self.vis_image is None:
                continue
            cv2.imshow('bev seg camera agent %s' % self.agent_id,
                       self.vis_image)
            cv2.waitKey(1)

    def destroy(self):
        self.sensor.destroy()
        cv2.destroyAllWindows()
