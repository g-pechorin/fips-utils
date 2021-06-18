'''
compress.py

compress and embed trees of files into your workspace
'''

Version = 1

import sys
import os.path
import yaml
import genutil


#-------------------------------------------------------------------------------
def generate(input, out_src, out_hdr) :
	if genutil.isDirty(Version, [input], [out_hdr]) :
		with open(input, 'r') as f :
			conf = yaml.load(f)
		
		# strip the zlib checksums
		strip = True
		if 'strip' in conf:
			strip = strip and conf['strip']
		
		line = 32
		if 'line' in conf:
			line = conf['line']
		
		# where to scan for files, what to include, then what to remove from that
		root = conf['root']

		# build the/a full list of files to include
		def sub(path):
			out = []
			for file in os.listdir(path):
				if os.path.isfile(os.path.join(path, file)):
					out.append(file)
				else:
					for baby in sub(os.path.join(path, file)):
						out.append(file + '/' + baby)
			return out
		full = sub(root)

		with open(out_hdr, 'w') as f:
			f.write('// #version:{}#\n'.format(Version))
			f.write('// machine generated, do not edit!\n')
			
			idx = -1
			items = []
			for name in full:
				with open(os.path.join(root, name), 'rb') as file:
					raw = file.read()
					if 0 == len(raw):
						items.append('\t{{ "{}", true, nullptr, 0, nullptr, 0 }},\n'.format(name))
					else:
						idx += 1
						import zlib
						zip = zlib.compress(raw, zlib.Z_BEST_COMPRESSION)
						if strip:
							# strip the two lead bytes so we don't need TINFL_FLAG_PARSE_ZLIB_HEADER
							zip = zip[2:]

						f.write('static uint8_t raw{}[{}];\n'.format(idx, len(raw)))
						f.write('static const uint8_t zip{}[{}] = {{\n\t'.format(idx, len(zip)))

						num = 0
						for byte in zip:
							if sys.version_info[0] >= 3:
								f.write(hex(ord(chr(byte))) + ', ')
							else:
								f.write(hex(ord(byte)) + ', ')
							num += 1
							if 0 == num % line:
								f.write('\n\t')

						f.write('\n};\n')

						items.append('\t{{ "{}", false, zip{}, {}, raw{}, {} }},\n'.format(name, idx, len(zip), idx, len(raw)))
			
			f.write('struct item_t { const char* _name; bool _hot; const uint8_t* _zip_data; const size_t _zip_size; uint8_t*const _raw_data; const size_t _raw_size; };\n')
			f.write('item_t item_p[] = {\n');
			for item in items:
				f.write(item)

			f.write('\n\t{nullptr}\n');
			f.write('};\n');
