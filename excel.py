import pandas as pd
import streamlit as st
import os
import json
from openai import OpenAI

# 初始化 DeepSeek API 客户端
client = OpenAI(
    api_key="sk-41000397bf374eb995c6846d6bf226aa",  # 替换为你的 DeepSeek API 密钥
    base_url="https://api.deepseek.com/v1"  # DeepSeek 的 API 地址
)

# 保存代码的目录
SAVED_CODES_DIR = "saved_codes"
if not os.path.exists(SAVED_CODES_DIR):
    os.makedirs(SAVED_CODES_DIR)

# Streamlit 界面
st.title("智能数据处理助手")

# 保存和恢复会话状态
if "processed_df" not in st.session_state:
    st.session_state.processed_df = None
if "generated_code" not in st.session_state:
    st.session_state.generated_code = None
if "navigation" not in st.session_state:
    st.session_state.navigation = "上传文件处理"

# 选择导航模式
navigation = st.sidebar.radio("选择操作模式", ["上传文件处理", "查看保存的代码"], index=["上传文件处理", "查看保存的代码"].index(st.session_state.navigation))
st.session_state.navigation = navigation  # 保存导航状态

if navigation == "上传文件处理":
    # 上传文件
    uploaded_file = st.file_uploader("上传 Excel 文件", type=["xlsx", "csv"])

    if uploaded_file:
        # 检测表头行
        raw_data = pd.read_excel(uploaded_file, header=None) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file, header=None)

        # 自动检测表头：寻找第一行非空的作为表头
        possible_header_row = raw_data.notnull().all(axis=1).idxmax()
        st.write(f"自动检测到的表头行：第 {possible_header_row + 1} 行")
        
        # 用户选择表头行
        header_row = st.number_input("请确认表头行（从 0 开始计数）", min_value=0, max_value=len(raw_data) - 1, value=possible_header_row)
        df = pd.read_excel(uploaded_file, header=header_row) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file, header=header_row)

        st.write("表格预览：")
        st.dataframe(df)

        # 提取表头
        headers = df.columns.tolist()
        st.write("表头信息：", headers)

        # 用户输入自然语言描述
        user_input = st.text_area("描述数据处理需求，例如：'将销售额列乘以2，并计算总和。'")
        
        if user_input and st.button("开始处理"):
            # 调用 DeepSeek 模型
            with st.spinner("正在处理数据..."):
                try:
                    # 构建请求消息
                    messages = [
                        {"role": "system", "content": "You are a data processing assistant."},
                        {"role": "user", "content": f"列名包括：{headers}。请根据以下需求生成 pandas 代码，不需要其它任何的解释，只需要代码：{user_input}"}
                    ]

                    response = client.chat.completions.create(
                        model="deepseek-chat",
                        messages=messages,
                        stream=False
                    )

                    # 提取代码段
                    generated_code = response.choices[0].message.content

                    # 检测代码是否在 ```python 和 ``` 标记之间
                    if "```python" in generated_code and "```" in generated_code:
                        code_start = generated_code.find("```python") + len("```python")
                        code_end = generated_code.rfind("```")
                        extracted_code = generated_code[code_start:code_end].strip()
                        st.session_state.generated_code = extracted_code  # 保存到会话状态
                        st.write("生成的代码：")
                        st.code(extracted_code, language="python")

                        # 执行代码
                        exec_locals = {"df": df}
                        try:
                            exec(extracted_code, {}, exec_locals)
                            st.session_state.processed_df = exec_locals.get("df", None)  # 保存结果到会话状态

                            # 显示结果
                            if st.session_state.processed_df is not None:
                                st.write("处理后的数据：")
                                st.dataframe(st.session_state.processed_df)

                                # 下载处理后的文件
                                output_file = "processed_data.xlsx"
                                st.session_state.processed_df.to_excel(output_file, index=False)
                                with open(output_file, "rb") as file:
                                    st.download_button(
                                        label="下载处理后的数据",
                                        data=file,
                                        file_name="processed_data.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                        except Exception as exec_error:
                            st.error(f"执行生成代码时出错：{exec_error}")

                        # 保存代码功能
                        with st.form("save_code_form"):
                            st.write("保存代码")
                            title = st.text_input("代码标题")
                            code_description = st.text_area("代码描述")
                            file_description = st.text_area("文件描述")
                            submitted = st.form_submit_button("保存代码")
                            if submitted:
                                if title and code_description and file_description:
                                    save_path = os.path.join(SAVED_CODES_DIR, f"{title}.json")
                                    if os.path.exists(save_path):
                                        st.error("同名标题已存在，请使用其他标题！")
                                    else:
                                        with open(save_path, "w") as f:
                                            json.dump({
                                                "title": title,
                                                "code": extracted_code,
                                                "code_description": code_description,
                                                "file_description": file_description
                                            }, f)
                                        st.success("代码保存成功！")
                                else:
                                    st.error("请填写所有字段后再保存！")
                    else:
                        st.error("生成的代码不包含正确的标记，请检查输出。")

                except Exception as e:
                    st.error(f"处理失败：{e}")

elif navigation == "查看保存的代码":
    # 查看保存的代码
    saved_files = [f for f in os.listdir(SAVED_CODES_DIR) if f.endswith(".json")]
    if saved_files:
        selected_file = st.selectbox("选择保存的代码文件", saved_files)
        if selected_file:
            with open(os.path.join(SAVED_CODES_DIR, selected_file), "r") as f:
                code_data = json.load(f)
                st.write(f"标题：{code_data['title']}")
                st.write(f"代码描述：{code_data['code_description']}")
                st.write(f"文件描述：{code_data['file_description']}")
                st.code(code_data['code'], language="python")

            # 允许用户重新上传文件并使用保存的代码
            uploaded_file = st.file_uploader("重新上传文件以执行保存的代码", type=["xlsx", "csv"])
            if uploaded_file:
                df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
                exec_locals = {"df": df}
                try:
                    exec(code_data["code"], {}, exec_locals)
                    processed_df = exec_locals.get("df", None)
                    if processed_df is not None:
                        st.write("处理后的数据：")
                        st.dataframe(processed_df)

                        # 下载结果
                        output_file = "processed_data.xlsx"
                        processed_df.to_excel(output_file, index=False)
                        with open(output_file, "rb") as file:
                            st.download_button(
                                label="下载处理后的数据",
                                data=file,
                                file_name="processed_data.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    else:
                        st.error("无法执行保存的代码。")
                except Exception as e:
                    st.error(f"执行保存的代码时出错：{e}")
    else:
        st.write("没有保存的代码。")