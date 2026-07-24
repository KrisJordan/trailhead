from pathlib import Path
import numpy as np
from package.absolute import ABSOLUTE_VALUE
from .relative import RELATIVE_VALUE
run_count = globals().get('run_count', 0) + 1
asset_hex = Path('assets/message.bin').read_bytes().hex()
print(f'{ABSOLUTE_VALUE} + {RELATIVE_VALUE}: Trailhead ☃ 你好')
print(f'numpy-sum:{int(np.array([2, 3]).sum())}')
print(f'asset:{asset_hex}')
print(f'clean-state:{run_count}')
