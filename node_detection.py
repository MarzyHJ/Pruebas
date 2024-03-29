import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool,Int8,Float64,Header,Int32
from geometry_msgs.msg import Twist,Point
from sensor_msgs.msg import Image
from custom_interfaces.msg import CA
from cv_bridge import CvBridge
import numpy as np
import time
import cv2
import pyzed.sl as sl
import math


class Detections(Node):
   
	def __init__(self):
		super().__init__("Detection_node")
		self.publisher_ = self.create_publisher(Image, 'camera/image', 10)
		self.center_approach = self.create_publisher(CA,"center_approach",10)
		self.twist = Twist()
		self.found_aruco = self.create_publisher(Bool, "detected_aruco", 1)
		self.found_orange = self.create_publisher(Bool, "detected_orange", 1)
		self.CA = CA()
		self.bridge = CvBridge()
		self.state_pub = self.create_publisher(Int8, "state", 1)
		self.create_subscription(Int8, "state", self.update_state, 1)
		
		self.vel_x = 0.33
		self.vel_y = 0
		self.vel_theta = 0.1
		
		self.x = 0
		self.y = 0
		self.distance = None
		self.contador = 0
		self.aruco_dis = False
		self.orange_dis = False
		self.is_center = False
		self.state = -1

		self.ARUCO_DICT = {
			"DICT_4X4_50": cv2.aruco.DICT_4X4_50,
			"DICT_4X4_100": cv2.aruco.DICT_4X4_100,
			"DICT_4X4_250": cv2.aruco.DICT_4X4_250,
			"DICT_4X4_1000": cv2.aruco.DICT_4X4_1000,
			"DICT_5X5_50": cv2.aruco.DICT_5X5_50,
			"DICT_5X5_100": cv2.aruco.DICT_5X5_100,
			"DICT_5X5_250": cv2.aruco.DICT_5X5_250,
			"DICT_5X5_1000": cv2.aruco.DICT_5X5_1000,
			"DICT_6X6_50": cv2.aruco.DICT_6X6_50,
			"DICT_6X6_100": cv2.aruco.DICT_6X6_100,
			"DICT_6X6_250": cv2.aruco.DICT_6X6_250,
			"DICT_6X6_1000": cv2.aruco.DICT_6X6_1000,
			"DICT_7X7_50": cv2.aruco.DICT_7X7_50,
			"DICT_7X7_100": cv2.aruco.DICT_7X7_100,
			"DICT_7X7_250": cv2.aruco.DICT_7X7_250,
			"DICT_7X7_1000": cv2.aruco.DICT_7X7_1000,
			"DICT_ARUCO_ORIGINAL": cv2.aruco.DICT_ARUCO_ORIGINAL,
			"DICT_APRILTAG_16h5": cv2.aruco.DICT_APRILTAG_16h5,
			"DICT_APRILTAG_25h9": cv2.aruco.DICT_APRILTAG_25h9,
			"DICT_APRILTAG_36h10": cv2.aruco.DICT_APRILTAG_36h10,
			"DICT_APRILTAG_36h11": cv2.aruco.DICT_APRILTAG_36h11
		}
		self.aruco_type = "DICT_4X4_50"
		self.arucoDict = cv2.aruco.Dictionary_get(self.ARUCO_DICT[self.aruco_type])
		self.arucoParams = cv2.aruco.DetectorParameters_create()
		
		self.zed = sl.Camera()

		self.quality = 18 
		self.create_subscription(Int8, "image_quality", self.quality_callback, 1)


		# Create a InitParameters object and set configuration parameters
		self.init_params = sl.InitParameters()
		self.init_params.depth_mode = sl.DEPTH_MODE.ULTRA  # Use ULTRA depth mode
		self.init_params.coordinate_units = sl.UNIT.MILLIMETER  # Use meter units (for depth measurements)

		# Open the camera
		status = self.zed.open(self.init_params)
		if status != sl.ERROR_CODE.SUCCESS: #Ensure the camera has opened succesfully
			print("Camera Open : "+repr(status)+". Exit program.")
			exit()

		# Create and set RuntimeParameters after opening the camera
		self.runtime_parameters = sl.RuntimeParameters()
		self.image = sl.Mat()
		self.depth = sl.Mat()
		self.point_cloud = sl.Mat()
		
		self.image_ocv = self.image.get_data()
		self.image_ocv = self.image_ocv[:,:-1]
		self.depth_ocv = self.image.get_data()
		self.quality = 18
		
		self.mirror_ref = sl.Transform()
		self.mirror_ref.set_translation(sl.Translation(2.75,4.0,0)) 

		#self.curr_signs_image_msg = self.cv2_to_imgmsg(self.image_ocv)

		self.timer = self.create_timer(0.001,self.detect)
	
	def orange_display(self, contours, image):

		if contours:
			self.orange_dis = True
			self.contador += 1
			
			for (idx, contour) in enumerate(contours):
				x, y, w, h = cv2.boundingRect(contour)

				corners = np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], dtype = np.int32)
				corners = corners.reshape((-1, 1, 2))

				cv2.polylines(image, [corners], isClosed=True, color=(0, 255, 0), thickness=2)

				cx = int(x + w / 2.0)
				cy = int(y + h / 2.0)
				print(f"x,y: {cx}, {cy}")
				self.x = cx
				self.y = cy
				print("Objeto naranja detectado")

		else:
			self.orange_dis = False
			self.contador = 0
			print("Objeto naranja no detectado")

		return image
	
	def aruco_display(self,corners, ids, rejected, image):
		
		if len(corners) > 0:
			ids = ids.flatten()
			self.aruco_dis = True
			self.contador +=1  
			for (markerCorner, markerID) in zip(corners, ids):
				
				corners = markerCorner.reshape((4, 2))
				(topLeft, topRight, bottomRight, bottomLeft) = corners

				topRight = (int(topRight[0]), int(topRight[1]))
				bottomRight = (int(bottomRight[0]), int(bottomRight[1]))
				bottomLeft = (int(bottomLeft[0]), int(bottomLeft[1]))
				topLeft = (int(topLeft[0]), int(topLeft[1]))
				cv2.line(image, topLeft, topRight, (0, 255, 0), 2)
				cv2.line(image, topRight, bottomRight, (0, 255, 0), 2)
				cv2.line(image, bottomRight, bottomLeft, (0, 255, 0), 2)
				cv2.line(image, bottomLeft, topLeft, (0, 255, 0), 2)
				cX = int((topLeft[0] + bottomRight[0]) / 2.0)
				cY = int((topLeft[1] + bottomRight[1]) / 2.0)
				cv2.circle(image, (cX, cY), 4, (0, 0, 255), -1)
				print(f"x,y: {cX},{cY}")
				self.x=cX
				self.y=cY
				cv2.putText(image, str(markerID),(topLeft[0], topLeft[1] - 10), cv2.FONT_HERSHEY_SIMPLEX,
					0.5, (0, 255, 0), 2)
				
				print("[Inference] ArUco marker ID: {}".format(markerID))      
		else:
			self.aruco_dis=False
			self.contador=0       
		return image

  # Listener de calidad de Imagen
	def quality_callback(self, msg):
		self.quality = msg.data

	def cv2_to_imgmsg(self, image):
		msg = self.bridge.cv2_to_imgmsg(image, encoding = "bgra8")
		return msg

	def cv2_to_imgmsg_resized(self, image, scale_percent):
		widht = int(image.shape[1] * scale_percent / 100)
		height = int(image.shape[0] * scale_percent / 100)
		dim = (widht, height)
		resized_image = cv2.resize(image, dim, interpolation = cv2.INTER_AREA)
		msg = self.bridge.cv2_to_imgmsg(resized_image, encoding = "bgra8")
		return msg
	
	def update_state(self, msg):
		self.state = msg.data

	def contornos(self, image):

		# Obtener los valores actuales de color
		orange_low_hue = 5
		orange_high_hue = 22
		orange_low_saturation = 130
		orange_high_saturation = 255
		orange_low_value = 160
		orange_high_value = 255

		# Convertir el fotograma al espacio de color HSV
		frame_hsv = cv2.cvtColor(self.image_ocv, cv2.COLOR_BGR2HSV)

		# Definir los umbrales de color naranja en el espacio de color HSV
		lower_orange = np.array([orange_low_hue, orange_low_saturation, orange_low_value])
		upper_orange = np.array([orange_high_hue, orange_high_saturation, orange_high_value])

		# Crear una máscara para detectar objetos de color naranja
		mask = cv2.inRange(frame_hsv, lower_orange, upper_orange)

		# Encontrar contornos en la máscara
		contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
		return contours
	
	def detect(self):
		if self.state == 3:
			if self.zed.grab(self.runtime_parameters) == sl.ERROR_CODE.SUCCESS:
				# Retrieve left image
				self.zed.retrieve_image(self.image, sl.VIEW.LEFT)
				self.image_ocv = self.image.get_data()
				# Retrieve depth map. Depth is aligned on the left image
				self.zed.retrieve_measure(self.depth, sl.MEASURE.DEPTH)
				self.depth_ocv = self.depth.get_data()
				# Retrieve colored point cloud. Point cloud is aligned on the left image.
				self.zed.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)

				self.corners = self.contornos(self.image_ocv)

				detected_orange = self.orange_display(self.corners, self.image_ocv)

				if self.corners:

					ht, wd = self.image_ocv.shape[:2]

					# Encontrar el contorno más grande
					max_contour = max(self.corners, key=cv2.contourArea)

					# Obtener el rectángulo delimitador
					x, y, w, h = cv2.boundingRect(max_contour)

					# Calcular el centro del objeto naranja
					centro_objeto = (x + w // 2, y + h // 2)

					# Calcular el centro de la imagen
					centro_imagen = (wd // 2, ht // 2)

					# Determinar la posición relativa
					if centro_objeto[0] < centro_imagen[0] - 50:
						self.posicion = "A la izquierda"
						print("A la izquierda")
					elif centro_objeto[0] > centro_imagen[0] + 50:
						self.posicion = "A la derecha"
						print("A la derecha")
					else:
						self.posicion = "Centrado"
						print("Centrado")

					# Dibujar un rectángulo alrededor del objeto naranja
					cv2.rectangle(self.image_ocv, (x, y), (x + w, y + h), (0, 255, 0), 2)

					cv2.putText(self.image_ocv, 'Naranja', (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

					err, point_cloud_value = self.point_cloud.get_value(self.x, self.y)
					#distance = 0
					if math.isfinite(point_cloud_value[2]):
						detected = Bool()
						if self.contador >= 2:
							detected.data = True
							self.found_orange.publish(detected)
							self.distance = math.sqrt(point_cloud_value[0] * point_cloud_value[0] +
												point_cloud_value[1] * point_cloud_value[1] +
												point_cloud_value[2] * point_cloud_value[2])
							print(f"Distance to Object at {{{self.x};{self.y}}}: {self.distance}")
							print(f"Contador: {self.contador}")
							
							self.x_zed = round(self.image.get_width() / 2)
							self.y_zed = round(self.image.get_height() / 2)
							cv2.circle(detected_orange, (self.x_zed, self.y_zed),4,(0,0,255),-1)
							
							print(f"x_z: {self.x_zed} y_z: {self.y_zed}")
							
							self.CA.distance = self.distance
							self.CA.x = self.x - self.x_zed
							if self.x > (self.x_zed+20):
								print(f"Objeto a la derecha por: {self.x_zed - self.x} pixeles")
								self.CA.detected = False
							elif self.x < (self.x_zed-20):
								print(f"Objeto a la izquierda por: {self.x - self.x_zed} pixeles")
								self.CA.detected = False
							elif self.x >= (self.x_zed-20) and self.x <= (self.x_zed+20):
								print(f"Objeto al centro")
								cv2.putText(detected_orange, f"Centro", (self.x, self.y -80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
								self.CA.detected = True
							self.center_approach.publish(self.CA)
						else:
							self.distance=None
							print("Not detected ",self.orange_dis)

					cv2.putText(detected_orange, f"Distancia: {self.distance}", (x, y - 64), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
					cv2.putText(detected_orange, f"Posicion: {self.posicion}", (x, y - 37), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
					self.publisher_.publish(self.cv2_to_imgmsg_resized(detected_orange, self.quality))
					self.get_logger().info("Publicando video")
				
				else:      
					self.cv2_to_imgmsg(detected_orange)
					self.publisher_.publish(self.cv2_to_imgmsg_resized(detected_orange, self.quality))
					self.get_logger().info("Publicando video sin deteccion")

		elif self.state == 4:
			if self.zed.grab(self.runtime_parameters) == sl.ERROR_CODE.SUCCESS:
				# Retrieve left image
				self.zed.retrieve_image(self.image, sl.VIEW.LEFT)
				self.image_ocv = self.image.get_data()
				# Retrieve depth map. Depth is aligned on the left image
				self.zed.retrieve_measure(self.depth, sl.MEASURE.DEPTH)
				self.depth_ocv = self.depth.get_data()
				# Retrieve colored point cloud. Point cloud is aligned on the left image.
				self.zed.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
		
				grayimg = cv2.cvtColor(self.image_ocv, cv2.COLOR_BGR2GRAY)
				#grayimgD = cv2.cvtColor(depth_ocv, cv2.COLOR_BGR2GRAY)
				corners, ids, rejected = cv2.aruco.detectMarkers(grayimg, self.arucoDict, parameters=self.arucoParams)
				detected_markers = self.aruco_display(corners, ids, rejected, self.image_ocv)
				
				# Get and print distance value in mm at the center of the image
				# We measure the distance camera - object using Euclidean distance
				
				err, point_cloud_value = self.point_cloud.get_value(self.x, self.y)
				#distance = 0
				if math.isfinite(point_cloud_value[2]):
					detected = Bool()
					if self.contador >= 2:
						detected.data = True
						self.found_aruco.publish(detected)
						self.distance = math.sqrt(point_cloud_value[0] * point_cloud_value[0] +
											point_cloud_value[1] * point_cloud_value[1] +
											point_cloud_value[2] * point_cloud_value[2])
						print(f"Distance to Aruco at {{{self.x};{self.y}}}: {self.distance}")
						print(f"Contador: {self.contador}")
						
						self.x_zed = round(self.image.get_width() / 2)
						self.y_zed = round(self.image.get_height() / 2)
						cv2.circle(detected_markers, (self.x_zed, self.y_zed),4,(0,0,255),-1)
						
						print(f"x_z: {self.x_zed} y_z: {self.y_zed}")
						
						self.CA.distance = self.distance
						self.CA.x = self.x - self.x_zed

						if self.x > (self.x_zed+20):
							print(f"Aruco a la derecha por: {self.x_zed - self.x} pixeles")
							self.CA.detected = False
						elif self.x < (self.x_zed-20):
							print(f"Aruco a la izquierda por: {self.x - self.x_zed} pixeles")
							self.CA.detected = False
						elif self.x >= (self.x_zed-20) and self.x <= (self.x_zed+20):
							print(f"Aruco al centro")
							cv2.putText(detected_markers, f"Centro", (self.x, self.y -80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
							self.CA.detected = True
							
						self.center_approach.publish(self.CA)
					else:
						self.distance=None
						print("Not detected ",self.aruco_dis)
			cv2.putText(detected_markers, f"Distancia: {self.distance}", (self.x, self.y -70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
			self.publisher_.publish(self.cv2_to_imgmsg_resized(detected_markers, self.quality))
			self.get_logger().info("Publicando video")

def main(args=None):
	rclpy.init(args=args)
	detect = Detections()
	rclpy.spin(detect)
	detect.zed.close()
	detect.destroy_node()
	rclpy.shutdown()
	
if __name__=="__main__":
	main()
	
