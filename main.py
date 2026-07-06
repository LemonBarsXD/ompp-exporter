import os
import csv
import sys
import tempfile
import concurrent.futures
from functools import partial
from maniera.calculator import Maniera

def process_map(full_path, target_mods=0, target_score=1000000):
    """
    Worker function that runs entirely isolated on its own CPU core.
    Parses metadata quickly, filters non-mania maps, and calculates PP.
    """
    metadata = {
        'title': 'Unknown Title',
        'artist': 'Unknown Artist',
        'version': 'Unknown Difficulty',
        'is_mania': False
    }
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            in_general = False
            in_metadata = False
            
            for line in f:
                line = line.strip()
                
                if line.startswith('[TimingPoints]') or line.startswith('[HitObjects]'):
                    break
                    
                if line == '[General]':
                    in_general = True
                    in_metadata = False
                    continue
                elif line == '[Metadata]':
                    in_metadata = True
                    in_general = False
                    continue
                elif line.startswith('[') and line.endswith(']'):
                    in_general = False
                    in_metadata = False
                    continue
                
                if in_general and line.startswith('Mode:'):
                    if line.split(':', 1)[1].strip() == '3':
                        metadata['is_mania'] = True
                        
                if in_metadata:
                    if line.startswith('Title:'):
                        metadata['title'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Artist:'):
                        metadata['artist'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Version:'):
                        metadata['version'] = line.split(':', 1)[1].strip()
                        
    except Exception:
        return None

    if not metadata['is_mania']:
        return None

    temp_fd, temp_path = tempfile.mkstemp(suffix='.osu', text=True)
    
    try:
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f_in:
            content = f_in.read()
            
        with os.fdopen(temp_fd, 'w', encoding='ascii', errors='ignore') as f_out:
            f_out.write(content)
            
        calc = Maniera(temp_path, target_mods, target_score)
        calc.calculate()
        
        return {
            'Title': metadata['title'],
            'Artist': metadata['artist'],
            'Difficulty': metadata['version'],
            'Stars': round(calc.sr, 2),
            'PP': round(calc.pp, 2)
        }
    except Exception:
        return None
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

def main():
    local_app_data = os.environ.get('LOCALAPPDATA')
    if not local_app_data:
        print("Could not find LOCALAPPDATA environment variable.")
        return
        
    songs_dir = os.path.join(local_app_data, 'osu!', 'Songs')
    
    if not os.path.exists(songs_dir):
        print(f"osu! Songs directory not found at: {songs_dir}")
        return
        
    titles = ['Title', 'Artist', 'Difficulty', 'Stars', 'PP']
    print("Choose what to sort by:")
    for i in range(len(titles)):
        print(f"{i+1}: {titles[i]}")
    print(f"{len(titles)+1}: All (Export multiple CSVs)")

    sort_options_to_process = []
    while True:
        user_input = input("> ")
        try:
            choice = int(user_input)
            if 1 <= choice <= len(titles):
                sort_options_to_process.append(titles[choice - 1])
                break
            elif choice == len(titles) + 1:
                sort_options_to_process = titles.copy()
                break
            else:
                print(f"Invalid choice. Please enter a number between 1 and {len(titles) + 1}.")
        except ValueError:
            print("Invalid input. Please enter a valid number.")

    print(f"\nScanning osu! Songs folder: {songs_dir}...")
    
    all_osu_files = []
    for root, dirs, files in os.walk(songs_dir):
        for file in files:
            if file.endswith('.osu'):
                all_osu_files.append(os.path.join(root, file))
                
    print(f"Found {len(all_osu_files)} total .osu files. Starting multi-core calculation...")
    
    results = []
    TARGET_MODS = 0
    TARGET_SCORE = 1000000

    worker = partial(process_map, target_mods=TARGET_MODS, target_score=TARGET_SCORE)

    with concurrent.futures.ProcessPoolExecutor() as executor:
        for i, result in enumerate(executor.map(worker, all_osu_files)):
            sys.stdout.write(f"\rProcessed {i+1} / {len(all_osu_files)} files...", )
                
            if result is not None:
                results.append(result)

    print("\n" + "="*40)
    for sort_title in sort_options_to_process:
        csv_filename = f"sorted_by_{sort_title}_export.csv"
        
        current_results = sorted(results, key=lambda x: x[sort_title], reverse=True)
        
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Title', 'Artist', 'Difficulty', 'Stars', 'PP']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for row in current_results:
                writer.writerow(row)
                
        print(f"Saved: {os.path.abspath(csv_filename)}")
        
    print("-" * 40)
    print(f"Done! Successfully processed {len(results)} mania maps.")
    print("="*40)

if __name__ == "__main__":
    main()
