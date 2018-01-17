#!/usr/bin/env python
import rospy
from std_msgs.msg import Int32
from geometry_msgs.msg import PoseStamped, Pose
from styx_msgs.msg import TrafficLightArray, TrafficLight
from styx_msgs.msg import Lane
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from light_classification.tl_classifier import TLClassifier
import tf
import cv2
import yaml
import math

STATE_COUNT_THRESHOLD = 3

class TLDetector(object):
    def __init__(self):
        rospy.init_node('tl_detector')

        self.pose = None
        self.waypoints = None
        self.camera_image = None
        self.lights = []

        sub1 = rospy.Subscriber('/current_pose', PoseStamped, self.pose_cb, queue_size=1)
        sub2 = rospy.Subscriber('/base_waypoints', Lane, self.waypoints_cb, queue_size=1)

        '''
        /vehicle/traffic_lights provides you with the location of the traffic light in 3D map space and
        helps you acquire an accurate ground truth data source for the traffic light
        classifier by sending the current color state of all traffic lights in the
        simulator. When testing on the vehicle, the color state will not be available. You'll need to
        rely on the position of the light and the camera image to predict it.
        '''
        sub3 = rospy.Subscriber('/vehicle/traffic_lights', TrafficLightArray, self.traffic_cb)
        sub6 = rospy.Subscriber('/image_color', Image, self.image_cb)

        config_string = rospy.get_param("/traffic_light_config")
        self.config = yaml.load(config_string)

        self.upcoming_red_light_pub = rospy.Publisher('/traffic_waypoint', Int32, queue_size=1)

        self.bridge = CvBridge()
        self.light_classifier = TLClassifier()
        self.listener = tf.TransformListener()

        self.state = TrafficLight.UNKNOWN
        self.last_state = TrafficLight.UNKNOWN
        self.last_wp = -1
        self.state_count = 0

        #rospy.spin()
        self.ros_spin()

    def ros_spin(self):
        rate = rospy.Rate(10) # 10 Hz spin rate
        while not rospy.is_shutdown():
            '''
            Publish upcoming red lights at camera frequency.
            Each predicted state has to occur `STATE_COUNT_THRESHOLD` number
            of times till we start using it. Otherwise the previous stable state is
            used.
            '''
            if self.pose is not None and self.waypoints is not None and self.has_image:
                light_wp, state = self.process_traffic_lights()
                if self.state != state:
                    self.state_count = 0
                    self.state = state
                elif self.state_count >= STATE_COUNT_THRESHOLD:
                    self.last_state = self.state
                    light_wp = light_wp if state == TrafficLight.RED else -1
                    self.last_wp = light_wp
                    self.upcoming_red_light_pub.publish(Int32(light_wp))
                else:
                    self.upcoming_red_light_pub.publish(Int32(self.last_wp))
                self.state_count += 1
            rate.sleep()

    def pose_cb(self, msg):
        self.pose = msg

    def waypoints_cb(self, waypoints):
        self.waypoints = waypoints

    def traffic_cb(self, msg):
        self.lights = msg.lights

    def image_cb(self, msg):
        """Identifies red lights in the incoming camera image and publishes the index
            of the waypoint closest to the red light's stop line to /traffic_waypoint

        Args:
            msg (Image): image from car-mounted camera

        """
        self.has_image = True
        self.camera_image = msg
        light_wp, state = self.process_traffic_lights()

    # TODO (SDG) - identical to function in wp_updater, move to a helpers file
    def _calc_dist(self, pos1, pos2):
        '''
        A helper method to return distance between two waypoints
        '''
        dist = math.sqrt((pos1.x - pos2.x)**2 + (pos1.y - pos2.y)**2)
        return dist

    # TODO (SDG) - identical to function in wp_updater, move to a helpers file
    def get_closest_waypoint(self, pose):
        """Identifies the closest path waypoint to the given position
            https://en.wikipedia.org/wiki/Closest_pair_of_points_problem
        Args:
            pose (Pose): position to match a waypoint to

        Returns:
            int: index of the closest waypoint in self.waypoints

        """
        closest_distance = 999999  # Initialise very high value
        closest_waypoint_idx = 0
        for idx, waypoint in enumerate(self.waypoints.waypoints):
            temp_dist = self._calc_dist(pose.position, waypoint.pose.pose.position)
            if (temp_dist < closest_distance):
                closest_distance = temp_dist
                closest_waypoint_idx = idx
        return closest_waypoint_idx

    def get_light_state(self, light):
        """Determines the current color of the traffic light

        Args:
            light (TrafficLight): light to classify

        Returns:
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        if(not self.has_image):
            self.prev_light_loc = None
            return False

        cv_image = self.bridge.imgmsg_to_cv2(self.camera_image, "bgr8")


        #Get classification
        # TODO - uncomment next line when classification is implemented
        traffic_light_stat = self.light_classifier.get_classification(cv_image)

        return traffic_light_stat

        # TODO - remove this line when classification is implemented
        # light.state is only provided for debugging purposes and is not available in the real car

        #return light.state

    def process_traffic_lights(self):
        """Finds closest visible traffic light, if one exists, and determines its
            location and color

        Returns:
            int: index of waypoint closes to the upcoming stop line for a traffic light (-1 if none exists)
            int: ID of traffic light color (specified in styx_msgs/TrafficLight)

        """
        light = None

        # List of positions that correspond to the line to stop in front of for a given intersection
        stop_line_positions = self.config['stop_line_positions']
        car_position = None
        if (self.pose):
            car_position = self.get_closest_waypoint(self.pose.pose)


        #TODO find the closest visible traffic light (if one exists)
        light_wp = None
        light = None
        min_dist_indices = 9999  # minimum distance in indices
        for index, traffic_light in enumerate(self.lights):
            if car_position:
                traffic_light_index = self.get_closest_waypoint(traffic_light.pose.pose)
                indices_to_traffic_light = traffic_light_index - car_position
                if indices_to_traffic_light > 0:  # traffic light is ahead of the car
                    if indices_to_traffic_light < min_dist_indices:
                        min_dist_indices = indices_to_traffic_light
                        light_wp = traffic_light_index
                        light = traffic_light

        if light:
            state = self.get_light_state(light)
            return light_wp, state
        self.waypoints = None
        return -1, TrafficLight.UNKNOWN

if __name__ == '__main__':
    try:
        TLDetector()
    except rospy.ROSInterruptException:
        rospy.logerr('Could not start traffic node.')
