FROM ubuntu:22.04

# Setup workspace directory
RUN mkdir /workspace
WORKDIR /workspace

# Install dependencies
ENV TZ=America/New_York
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install --yes \
        apt-transport-https \
        ca-certificates \
        cmake \
        curl \
        debian-keyring \
        debian-archive-keyring \
        git \
        gnupg \
        # libatomic1 \
        locales \
        software-properties-common \
        sudo \
        tzdata \
        unzip \
        wget \
        zip \
        zsh \
    && rm -rf /var/lib/apt/lists/*

# Install Caddy web server
RUN curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list \
    && apt update \
    && apt install caddy

# Install Node.js 20 from https://github.com/nodesource
ENV NODE_MAJOR 20 
RUN mkdir -p /etc/apt/keyrings \ 
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install nodejs -y \
    && npm install -g npm@latest \
    && rm -rf /var/lib/apt/lists/*

# Install Python 3.12
RUN add-apt-repository ppa:deadsnakes/ppa \
    && apt update \
    && apt install --yes \
        python3.12 \
        libpq-dev \
        python3.12-dev \
        python3.12-distutils \
        python3-pip \
        libcairo2 \
    && rm -rf /var/lib/apt/lists* \
    && unlink /usr/bin/python3 \
    && ln -s /usr/bin/python3.12 /usr/bin/python3

# Update PIP for 3.12 / Ubuntu compatibility (https://ubuntuhandbook.org/index.php/2023/10/fix-broken-pip-python-312-ubuntu/)
RUN wget -O /tmp/get-pip.py https://bootstrap.pypa.io/get-pip.py && \
    python3 /tmp/get-pip.py && \
    rm /tmp/get-pip.py

# Use a non-root user per https://code.visualstudio.com/remote/advancedcontainers/add-nonroot-user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# Add non-root user and add to sudoers
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME -s /usr/bin/zsh \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Give user ownership of node_modules volume
RUN mkdir -p /workspace/client/node_modules && chown $USERNAME /workspace/client/node_modules
VOLUME /workspace/client/node_modules

# Set code to default git commit editor
RUN git config --system core.editor "code --wait"
# Set Safe Directory
RUN git config --system safe.directory '/workspace'

# Set Locale for Functional Autocompletion in zsh
RUN locale-gen en_US.UTF-8

# Configure zsh
USER $USERNAME
ENV HOME /home/$USERNAME

# Add zsh theme with niceties
RUN curl https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh | bash - \
    && sed -i 's/robbyrussell/kennethreitz/g' ~/.zshrc \
    && echo 'export PATH=$PATH:$HOME/.local/bin:/workspace/bin' >>~/.zshrc

# Install Python requirements.txt
COPY server/requirements.txt /workspace/requirements.txt
WORKDIR /workspace
RUN echo 'export PYTHONPATH=/workspace/server/src' >>~/.zshrc && \
    python3 -m pip install -r requirements.txt
