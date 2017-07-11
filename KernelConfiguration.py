import re
import enum

class ConfigOptionState(enum.IntEnum):
	Disabled = 1
	Enabled = 2
	Module = 3

class KernelConfiguration(object):
	def __init__(self, filename):
		self._filename = filename
		self._keys = { }
		self._parse()

	def _parse(self):
		with open(self._filename) as f:
			for line in f:
				line = line.rstrip("\r\n")
				if not line.startswith("CONFIG_"):
					continue
				(key, value) = line.split("=", maxsplit = 1)
				key = key[7:]
				if value == "y":
					value = ConfigOptionState.Enabled
				elif value == "n":
					value = ConfigOptionState.Disabled
				elif value == "m":
					value = ConfigOptionState.Module
				self._keys[key] = value

	def __getitem__(self, key):
		return self._keys.get(key)
