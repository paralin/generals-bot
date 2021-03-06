'''
	@ Harris Christiansen (Harris@HarrisChristiansen.com)
	January 2016
	Generals.io Automated Client - https://github.com/harrischristiansen/generals-bot
	Generals Bot: Base Bot Class
'''

import logging
import os
from queue import Queue
import random
import threading
import time

from .client import generals

HAS_VIEWER = False
try:
	from .viewer import GeneralsViewer
	HAS_VIEWER = True
except:
	pass

# Opponent Type Definitions
OPP_EMPTY = 0
OPP_ARMY = 1
OPP_CITY = 2
OPP_GENERAL = 3

DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]

class GeneralsBot(object):
	def __init__(self, updateMethod, name="PurdueBot", gameType="private", privateRoomID="PurdueBot", gameViewer=True):
		# Save Config
		self._updateMethod = updateMethod
		self._name = name
		self._gameType = gameType
		self._privateRoomID = privateRoomID

		# ----- Start Game -----
		self._running = True
		self._move_event = threading.Event()

		# Start Game Thread
		_create_thread(self._start_game_thread)
		# Start Chat Message Thead
		_create_thread(self._start_chat_thread)
		# Start Game Move Thread
		_create_thread(self._start_moves_thread)

		# Start Game Viewer
		if (gameViewer) and HAS_VIEWER:
			window_title = "%s (%s)" % (self._name, self._gameType)
			self._viewer = GeneralsViewer(window_title)
			self._viewer.mainViewerLoop() # Consumes Main Thread
			os._exit(0) # End Program

		while (self._running):
			time.sleep(10)

		os._exit(0) # End Program

	######################### Handle Updates From Server #########################

	def _start_game_thread(self):
		# Create Game
		if (self._gameType == "ffa"): # FFA
			self._game = generals.Generals(self._name, self._name, 'ffa')
		elif (self._gameType == "1v1"): # 1v1
			self._game = generals.Generals(self._name, self._name, '1v1')
		else: # private
			self._game = generals.Generals(self._name, self._name, 'private', gameid=self._privateRoomID)

		# Start Receiving Updates
		try:
			for update in self._game.get_updates():
				self._set_update(update)

				# Perform Make Move
				#self._make_move()
				self._move_event.set()

				# Update GeneralsViewer Grid
				selfDir = dir(self)
				if '_viewer' in selfDir:
					if '_path' in selfDir:
						self._update.path = self._path
					if '_collect_path' in selfDir:
						self._update.collect_path = self._collect_path
					if '_moves_realized' in selfDir:
						self._update.bottomText = "Realized: "+str(self._moves_realized)
					self._viewer.updateGrid(self._update)
		except ValueError: # Already in match, restart
			logging.info("Exit: Already in match in _start_update_loop")
			time.sleep(45)
			os._exit(0) # End Program

	def _set_update(self, update):
		if (update.complete):
			logging.info("!!!! Game Complete. Result = " + str(update.result) + " !!!!")
			if '_moves_realized' in dir(self):
				logging.info("Moves: %d, Realized: %d" % (self._update.turn, self._moves_realized))
			self._running = False
			os._exit(0) # End Program
			return

		self._update = update

	######################### Move Generation #########################

	def _start_moves_thread(self):
		self._moves_realized = 0
		while (self._running):
			self._move_event.wait()
			self._move_event.clear()
			self._make_move()
			self._moves_realized+=1

	def _make_move(self):
		self._updateMethod(self, self._update)


	######################### Chat Messages #########################

	def _start_chat_thread(self):
		# Send Chat Messages
		while (self._running):
			msg = str(input('Send Msg:'))
			self._game.send_chat(msg)
			time.sleep(0.7)

		return

	######################### Tile Finding #########################

	def find_largest_tile(self, ofType=None, notInPath=[], includeGeneral=False): # ofType = Integer, notInPath = [Tile], includeGeneral = False|True|Int Acceptable Largest|0.1->0.9 Ratio
		if (ofType == None):
			ofType = self._update.player_index
		general = self._update.generals[ofType]

		largest = None
		for x in range(self._update.cols): # Check Each Square
			for y in range(self._update.rows):
				tile = self._update.grid[y][x]
				if (tile.tile == ofType and (largest == None or largest.army < tile.army)): # New Largest
					if ((tile not in notInPath) and tile != general): # Exclude Path and General
						largest = tile

		if (includeGeneral > 0 and general not in notInPath): # Handle includeGeneral
			if (includeGeneral < 1):
				includeGeneral = general.army * includeGeneral
				if (includeGeneral < 6):
					includeGeneral = 6
			if (largest == None): 
				largest = general
			elif (includeGeneral == True and largest.army < general.army):
				largest = general
			elif (includeGeneral > True and largest.army < general.army and largest.army <= includeGeneral):
				largest = general

		return largest

	def find_city(self, ofType=None, notOfType=None, notInPath=[], findLargest=True, includeGeneral=False): # ofType = Integer, notOfType = Integer, notInPath = [Tile], findLargest = Boolean
		if (ofType == None and notOfType == None):
			ofType = self._update.player_index

		found_city = None
		for city in self._update.cities: # Check Each City
			if (city in notInPath):
				continue

			if (city.tile == ofType or (notOfType != None and city.tile != notOfType)):
				if (found_city == None):
					found_city = city
				elif (findLargest and found_city.army < city.army) or (not findLargest and city.army < found_city.army):
					found_city = city

		if includeGeneral:
			general = self._update.generals[ofType]
			if (found_city == None):
				return general
			if (general != None and ((findLargest and general.army > found_city.army) or (not findLargest and general.army < found_city.army))):
				return general

		return found_city

	def find_closest_in_path(self, tile, path):
		closest = None
		closest_distance = 9999
		for dest in path:
			distance = self.distance(tile, dest)
			if (distance < closest_distance):
				closest = dest
				closest_distance = distance

		return closest

	def find_closest_target(self, source):
		max_target_army = source.army * 2 + 14

		closest = None
		closest_distance = 9999
		for x in range(self._update.cols): # Check Each Square
			for y in range(self._update.rows):
				dest = self._update.grid[y][x]
				if (dest.tile < generals.map.TILE_EMPTY or dest.tile == self._update.player_index or dest.army > max_target_army): # Non Target Tiles
					continue

				distance = self.distance(source, dest)
				if (dest in self._update.generals): # Generals appear closer
					distance = distance * 0.13
				elif (dest in self._update.cities): # Cities vary distance based on size, but appear closer
					distance = distance * sorted((0.18, (dest.army / (3.2*source.army)), 4))[1]
				elif (dest.tile == generals.map.TILE_EMPTY): # Empties appear further away
					distance = distance * 3.8

				if (dest.army > source.army): # Larger targets appear further away
					distance = distance * (1.5*dest.army/source.army)

				if (distance < closest_distance and self._validTarget(dest)):
					closest = dest
					closest_distance = distance

		return closest


	def find_primary_target(self, target=None):
		target_type = OPP_EMPTY - 1
		if (target != None and target.tile == self._update.player_index): # Acquired Target
			target = None
		if target != None: # Determine Previous Target Type
			target_type = OPP_EMPTY
			if target in self._update.generals:
				target_type = OPP_GENERAL
			elif target in self._update.cities:
				target_type = OPP_CITY
			elif target.army > 0:
				target_type = OPP_ARMY

		# Determine Max Target Size
		largest = self.find_largest_tile(includeGeneral=True)
		max_target_size = largest.army * 1.25

		for x in _shuffle(range(self._update.cols)): # Check Each Tile
			for y in _shuffle(range(self._update.rows)):
				source = self._update.grid[y][x]
				if (not self._validTarget(source)) or (source.tile == self._update.player_index): # Don't target invalid tiles
					continue

				if (target_type <= OPP_GENERAL): # Search for Generals
					if (source.tile >= 0 and source in self._update.generals and source.army < max_target_size):
						return source

				if (target_type <= OPP_CITY): # Search for Smallest Cities
					if (source in self._update.cities and source.army < max_target_size):
						if (target_type < OPP_CITY or source.army < target.army):
							target = source
							target_type = OPP_CITY

				if (target_type <= OPP_ARMY): # Search for Largest Opponent Armies
					if (source.tile >= 0 and (target == None or source.army > target.army) and source not in self._update.cities):
						target = source
						target_type = OPP_ARMY

				if (target_type < OPP_EMPTY): # Search for Empty Squares
					if (source.tile == generals.map.TILE_EMPTY and source.army < largest.army):
						target = source
						target_type = OPP_EMPTY

		return target

	######################### Pathfinding #########################

	def find_path(self, source=None, dest=None):
		# Verify Source and Dest
		if (source == None): # No Source, Use General
			source = self._update.generals[self._update.player_index]
		if (dest == None): # No Dest, Use Primary Target
			dest = self.find_primary_target()
		if (source==None or dest==None):
			return []

		# Determine Path To Destination
		frontier = Queue()
		frontier.put(source)
		came_from = {}
		came_from[source] = None

		while not frontier.empty():
			current = frontier.get()

			if current == dest: # Found Destination
				break

			for next in self._neighbors(current):
				if (next not in came_from) and (next not in self._update.cities or next==dest or next.tile == self._update.player_index): # Add to frontier
					#priority = self.distance(next, dest)
					frontier.put(next)
					came_from[next] = current

		# Create Path List
		path = self._path_reconstruct(came_from, dest)

		return path

	def _path_reconstruct(self, came_from, dest):
		current = dest
		path = [current]
		try:
			while came_from[current] != None:
				current = came_from[current]
				path.append(current)
		except KeyError:
			None
		path.reverse()

		return path

	def _neighbors(self, source):
		x = source.x
		y = source.y

		neighbors = []
		for dy, dx in DIRECTIONS:
			if (self.validPosition(x+dx, y+dy)):
				current = self._update.grid[y+dy][x+dx]
				if (current.tile != generals.map.TILE_OBSTACLE or current in self._update.cities or current in self._update.generals):
					neighbors.append(current)

		return neighbors
	

	######################### Movement Helpers #########################

	def path_forward_moves(self, path):
		if (len(path) < 2):
			return (None, None)

		# Find largest tile in path to move forward
		largest = path[0]
		largest_index = 0
		for i, tile in enumerate(path):
			if (tile == path[-1]):
				break
			if (tile.tile == path[0].tile and tile > largest):
				largest = tile
				largest_index = i

		dest = path[largest_index+1]
		return (largest, dest)

	def toward_dest_moves(self, source, dest=None):
		# Determine Destination
		if (dest == None):
			dest = self.find_primary_target()
			if (dest == None):
				return self.away_king_moves(source)

		# Compute X/Y Directions
		dir_y = 1
		if source.y > dest.y:
			dir_y = -1

		dir_x = 1
		if source.x > dest.x:
			dir_x = -1

		# Return List of Moves
		moves = random.sample([(0, dir_x), (dir_y, 0)],2)
		moves.extend(random.sample([(0, -dir_x), (-dir_y, 0)],2))
		return moves

	def away_king_moves(self, source):
		general = self._update.generals[self._update.player_index]

		if (source.y == general.y and source.x == general.x): # Moving from General
			return self.moves_random()

		dir_y = 1
		if source.y < general.y:
			dir_y = -1

		dir_x = 1
		if source.x < general.x:
			dir_x = -1

		moves = random.sample([(0, dir_x), (dir_y, 0)],2)
		moves.extend(random.sample([(0, -dir_x), (-dir_y, 0)],2))
		return moves

	def moves_random(self):
		return random.sample(DIRECTIONS, 4)

	def distance(self, source, dest):
		if source != None and dest != None:
			return abs(source.x - dest.x) + abs(source.y - dest.y)
		return 0

	def place_move(self, source, dest, move_half=False):
		if (self.validPosition(dest.x, dest.y)):
			self._game.move(source.y, source.x, dest.y, dest.x, move_half)
			return True
		return False

	def validPosition(self, x, y):
		return 0 <= y < self._update.rows and 0 <= x < self._update.cols and self._update._tile_grid[y][x] != generals.map.TILE_MOUNTAIN

	def _validTarget(self, target): # Check target to verify reachable
		for dy, dx in DIRECTIONS:
			if (self.validPosition(target.x+dx, target.y+dy)):
				tile = self._update.grid[target.y+dy][target.x+dx]
				if (tile.tile != generals.map.TILE_OBSTACLE or tile in self._update.cities or tile in self._update.generals):
					return True
		return False


######################### Global Helpers #########################

def _create_thread(f):
	t = threading.Thread(target=f)
	t.daemon = True
	t.start()

def _shuffle(seq):
	shuffled = list(seq)
	random.shuffle(shuffled)
	return iter(shuffled)
