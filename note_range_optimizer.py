import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from keyboard_mapping import NOTE_TO_KEY, PENTATONIC_INTERVALS, OCTAVE_BASES, GAME_NOTES, PLAY_MODES

class NoteRangeOptimizer:
    """音域优化处理类"""
    def __init__(self, mode='21key'):
        # 获取当前模式的配置
        self.mode_config = PLAY_MODES[mode]
        self.playable_min = self.mode_config['playable_min']
        self.playable_max = self.mode_config['playable_max']
        self.playable_range = self.playable_max - self.playable_min
        
        # 使用当前模式的映射
        self.target_notes = set(self.mode_config['note_to_key'].keys())
        self.octave_bases = self.mode_config['octave_bases']
        
        # 保持五声音阶定义
        self.pentatonic_intervals = PENTATONIC_INTERVALS
        
        # 音符权重配置
        self.weights = {
            'coverage': 0.4,      # 增加覆盖率权重
            'density': 0.1,       # 降低密度权重
            'melody': 0.3,        # 增加旋律线权重
            'transition': 0.1,    # 保持过渡权重
            'pentatonic': 0.05,   # 降低五声音阶匹配权重
            'octave_balance': 0.05 # 降低八度平衡权重
        }
        
        # 定义过渡音和装饰音的重要性
        self.transition_notes = {
            1: 0.9,   # 增加小二度重要性
            3: 0.8,   # 增加小三度重要性
            6: 0.7,   # 增加增四度重要性
            8: 0.8,   # 增加小六度重要性
            10: 0.7,  # 增加小七度重要性
        }
        
        # 缓存计算结果
        self._note_importance_cache = {}
        self._interval_cache = {}
    
    def analyze_notes(self, notes: List[int], velocities: Optional[List[int]] = None) -> Dict:
        """分析音符数据
        Args:
            notes: 音符列表
            velocities: 对应的力度列表(可选)
        Returns:
            音符分析结果
        """
        stats = {
            'min_note': min(notes),
            'max_note': max(notes),
            'range': max(notes) - min(notes),
            'distribution': self._get_note_distribution(notes),
            'melody_line': self._analyze_melody_line(notes),
            'transitions': self._analyze_transitions(notes),
            'density': self._analyze_density(notes)
        }
        
        if velocities:
            stats['velocity_map'] = self._analyze_velocities(notes, velocities)
            
        return stats
    
    def find_best_offset(self, notes: List[int], velocities: Optional[List[int]] = None) -> Tuple[int, float]:
        """找到最佳音域偏移量（改进版）"""
        stats = self.analyze_notes(notes, velocities)
        
        best_offset = 0
        best_score = 0
        
        # 计算原始音域的中心点
        original_center = (stats['min_note'] + stats['max_note']) / 2
        # 计算目标音域的中心点
        target_center = (self.playable_min + self.playable_max) / 2
        # 计算建议的基础偏移量
        suggested_offset = int(target_center - original_center)
        
        # 在建议偏移量附近搜索最佳值
        search_range = 12  # 在建议值上下一个八度范围内搜索
        min_offset = max(self.playable_min - stats['max_note'], suggested_offset - search_range)
        max_offset = min(self.playable_max - stats['min_note'], suggested_offset + search_range)
        
        for offset in range(int(min_offset), int(max_offset) + 1):
            score = self._calculate_fitness(stats, offset)
            if score > best_score:
                best_score = score
                best_offset = offset
        
        return best_offset, best_score
    
    def _get_note_distribution(self, notes: List[int]) -> Dict[int, int]:
        """获取音符分布"""
        distribution = defaultdict(int)
        for note in notes:
            distribution[note] += 1
        return dict(distribution)
    
    def _analyze_melody_line(self, notes: List[int]) -> Dict:
        """分析旋律线特征"""
        if not notes:
            return {}
            
        # 计算音高变化
        changes = np.diff(notes)
        
        return {
            'avg_change': float(np.mean(np.abs(changes))),
            'max_change': float(np.max(np.abs(changes))),
            'direction_changes': len([i for i in range(1, len(changes)) 
                                   if changes[i] * changes[i-1] < 0])
        }
    
    def _analyze_transitions(self, notes: List[int]) -> Dict:
        """分析音符转换特征"""
        transitions = defaultdict(int)
        for i in range(len(notes) - 1):
            transition = (notes[i], notes[i+1])
            transitions[transition] += 1
        return dict(transitions)
    
    def _analyze_density(self, notes: List[int]) -> Dict:
        """分析音符密度"""
        # 将音符按音高分组
        height_groups = defaultdict(int)
        for note in notes:
            height_groups[note // 12] += 1  # 按八度分组
            
        return {
            'total_notes': len(notes),
            'unique_notes': len(set(notes)),
            'octave_distribution': dict(height_groups)
        }
    
    def _analyze_velocities(self, notes: List[int], velocities: List[int]) -> Dict:
        """分析音符力度"""
        velocity_map = defaultdict(list)
        for note, vel in zip(notes, velocities):
            velocity_map[note].append(vel)
            
        # 计算每个音符的平均力度
        return {note: float(np.mean(vels)) for note, vels in velocity_map.items()}
    
    def _calculate_fitness(self, stats: Dict, offset: int) -> float:
        """计算适应度分数"""
        # 获取原始音符列表
        notes = list(stats['distribution'].keys())
        
        # 基础分数
        coverage_score = self._calculate_coverage_score(stats, offset)
        density_score = self._calculate_density_score(stats, offset)
        melody_score = self._calculate_melody_score(stats, offset)
        transition_score = self._calculate_transition_score(stats, offset)
        
        # 新增五声音阶相关分数
        pentatonic_score = self._calculate_pentatonic_score(notes, offset)
        octave_balance = self._calculate_octave_balance(notes, offset)
        
        # 综合得分
        total_score = (
            self.weights['coverage'] * coverage_score +
            self.weights['density'] * density_score +
            self.weights['melody'] * melody_score +
            self.weights['transition'] * transition_score +
            self.weights['pentatonic'] * pentatonic_score +
            self.weights['octave_balance'] * octave_balance
        )
        
        return total_score
    
    def _calculate_coverage_score(self, stats: Dict, offset: int) -> float:
        """计算音符覆盖率得分"""
        playable_notes = 0
        total_notes = sum(stats['distribution'].values())
        
        for note, count in stats['distribution'].items():
            shifted_note = note + offset
            if self.playable_min <= shifted_note <= self.playable_max:
                playable_notes += count
        
        return playable_notes / total_notes if total_notes > 0 else 0
    
    def _calculate_density_score(self, stats: Dict, offset: int) -> float:
        """计算音符密度得分"""
        # 检查偏移后的音符分布是否均匀
        shifted_distribution = defaultdict(int)
        for note, count in stats['distribution'].items():
            shifted_note = note + offset
            if self.playable_min <= shifted_note <= self.playable_max:
                shifted_distribution[shifted_note // 12] += count
                
        if not shifted_distribution:
            return 0
            
        # 计算分布的均匀性
        values = list(shifted_distribution.values())
        return 1 - (np.std(values) / np.mean(values)) if values else 0
    
    def _calculate_melody_score(self, stats: Dict, offset: int) -> float:
        """计算旋律线得分（改进版）"""
        melody_stats = stats['melody_line']
        if not melody_stats:
            return 0
            
        # 计算与原始音高的偏差
        original_notes = list(stats['distribution'].keys())
        shifted_notes = [note + offset for note in original_notes]
        
        # 计算平均偏差（越小越好）
        avg_deviation = sum(abs(s - o) for s, o in zip(shifted_notes, original_notes)) / len(original_notes)
        deviation_score = 1.0 / (1.0 + avg_deviation / 12.0)  # 归一化到0-1范围
        
        # 评估旋律跳进是否合理
        avg_change = melody_stats['avg_change']
        max_change = melody_stats['max_change']
        
        # 偏好保持原始的音程关系
        change_score = 1.0 - (avg_change / 12.0 if avg_change <= 12 else 1.0)
        
        # 综合得分，更重视保持原始音高
        return (deviation_score * 0.7 + change_score * 0.3)
    
    def _calculate_transition_score(self, stats: Dict, offset: int) -> float:
        """计算转换平滑度得分"""
        transitions = stats['transitions']
        if not transitions:
            return 0
            
        # 评估音符转换的平滑程度
        total_transitions = sum(transitions.values())
        smooth_transitions = sum(count for (n1, n2), count in transitions.items() 
                               if abs(n2 - n1) <= 12)  # 限制在一个八度内的跳进
        
        return smooth_transitions / total_transitions if total_transitions > 0 else 0 
    
    def _calculate_note_importance(self, interval: int) -> float:
        """计算音符的重要性（带缓存）"""
        if interval in self._note_importance_cache:
            return self._note_importance_cache[interval]
            
        if interval in self.pentatonic_intervals:
            importance = 1.0
        else:
            importance = self.transition_notes.get(interval, 0.3)
            
        self._note_importance_cache[interval] = importance
        return importance

    def _get_interval(self, note: int, base: int) -> int:
        """获取音程（带缓存）"""
        cache_key = (note, base)
        if cache_key in self._interval_cache:
            return self._interval_cache[cache_key]
            
        interval = (note - base) % 12
        self._interval_cache[cache_key] = interval
        return interval

    def _calculate_pentatonic_score(self, notes: List[int], offset: int) -> float:
        """计算五声音阶匹配度分数（改进版）"""
        score = 0
        total_notes = len(notes)
        
        for note in notes:
            shifted_note = note + offset
            best_note_score = 0
            
            for base in self.octave_bases.values():
                if base <= shifted_note < base + 12:
                    interval = self._get_interval(shifted_note, base)
                    # 计算音符重要性
                    importance = self._calculate_note_importance(interval)
                    # 计算与最近五声音阶音符的距离
                    min_distance = min(abs(interval - p_interval) 
                                     for p_interval in self.pentatonic_intervals)
                    # 使用距离和重要性计算得分
                    note_score = importance / (1.0 + min_distance * 0.5)
                    best_note_score = max(best_note_score, note_score)
            
            score += best_note_score
        
        return score / total_notes if total_notes > 0 else 0

    def _calculate_octave_balance(self, notes: List[int], offset: int) -> float:
        """计算八度平衡度分数（改进版）"""
        octave_counts = defaultdict(lambda: {'total': 0, 'important': 0})
        total_notes = len(notes)
        
        for note in notes:
            shifted_note = note + offset
            # 确定音符属于哪个八度
            if shifted_note < self.octave_bases['middle']:
                octave = 'low'
            elif shifted_note < self.octave_bases['high']:
                octave = 'middle'
            else:
                octave = 'high'
            
            # 计算音符重要性
            base = self.octave_bases[octave]
            interval = self._get_interval(shifted_note, base)
            importance = self._calculate_note_importance(interval)
            
            octave_counts[octave]['total'] += 1
            octave_counts[octave]['important'] += importance
        
        if total_notes == 0:
            return 0
        
        # 计算加权平衡度
        weights = {'low': 0.3, 'middle': 0.4, 'high': 0.3}  # 中音区权重略高
        balance_score = 0
        
        for octave, weight in weights.items():
            count = octave_counts[octave]
            if count['total'] > 0:
                # 考虑音符数量和重要性的平衡
                octave_score = (count['total'] / total_notes * 0.6 + 
                              count['important'] / total_notes * 0.4)
                balance_score += weight * octave_score
        
        return balance_score
#触发更新