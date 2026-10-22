# Skill：实现/修改默写判分逻辑

## 触发场景
涉及单词拼写比对、对错判定、掌握度更新。

## 步骤
1. 输入 normalize：trim、转小写
2. 判断严格模式 / 宽松模式（连字符、空格）
3. 查英美拼写映射表，命中则视为正确
4. 得出 is_correct
5. 更新 word_progress：
   - 正确 → correct_count +1；连续正确达 2 → mastery_level=2
   - 错误 → wrong_count +1；mastery_level=1；写入/累加 wrong_words
6. 记录 practice_records（user_input、is_correct、used_hint）
7. 返回：is_correct、mastery_level；仅错误时附正确拼写与例句

## 红线
- 判分只在服务端
- 出题接口不返回拼写
- 映射表单独维护，不写死在判分函数里
